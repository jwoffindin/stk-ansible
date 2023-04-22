#!/usr/bin/env python

"""
This module allows processing of STK-style CloudFormation templates as an Ansible module.

"""

from __future__ import absolute_import, division, print_function

import os
import re
from typing import Dict
import yaml

from ansible.module_utils.basic import AnsibleModule
from stk.template import Template, RenderedTemplate
from stk.template_helpers import TemplateHelpers
from stk.aws_config import AwsSettings
from stk.config import Config
from stk.stack import Stack
from stk.template_source import TemplateSource

__metaclass__ = type  # pylint: disable=invalid-name

DOCUMENTATION = r"""
---
module: template

short_description: Expose STK-compatible templating as an Ansible module

version_added: "1.0.0"

description: Allow use of stk templates from within Ansible

options:
    template:
        description: The filename of template to use
        required: true
        type: str or dict
    vars_file:
        description: The filename of the vars file to load
        required: false
        type: str
    vars:
        description: Parameters to pass to template
        required: false
        type: dict
    aws:
        description: AWS settings - required if using some stk helpers (e.g. user_data)
        required: false
        type: dict
author:
    - John Woffindin
"""

EXAMPLES = r"""
# Render a template in current directory passing in single variable 'role_name'
- template: my-template.yaml
  vars:
    foo: bar

# Render a template from remote git repository. This means you don't need to
# store the template in your Ansible repository.
# The template will be rendered using the latest commit on the default branch
- template:
    name: vpc.yaml
    repo: https://github.com/jwoffindin/stk-templates.git
  vars_file: vars.yaml
"""

RETURN = r"""
# These are examples of possible return values, and in general should use other names for return values.
content:
    description: Rendered template
    type: str
    returned: always
    sample: '....'
diff:
    description: Diff of rendered template vs currently deployed stack
    type: str
    returned: sometimes
error:
    description: Error message if any error occurred
    type: str
    returned: sometimes
    sample: 'Templating error'
"""


class MinimalConfig:
    """Minimal config object required for template helpers (e.g. for uploading lambdas)"""

    def __init__(self, aws: AwsSettings, tags: Dict, template_vars: Dict):
        self.aws = aws
        self.tags = tags
        self.vars = template_vars


def run_module():
    """entrypoint for Ansible module"""
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        action=dict(type="str", required=False, default="render"),
        template=dict(type="str", required=True),
        vars=dict(type="dict", required=False),
        vars_file=dict(type="str", required=False),
        aws=dict(type="dict", required=False),
        tags=dict(type="dict", required=False),
        helpers=dict(type="list", required=False, default=[]),
    )

    # seed the result dict in the object
    result = dict(changed=False, content="", error="")

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # Get 'action' parameter from module
    action = module.params["action"]

    # Template provider allows us to load templates from local directory or
    # remote git repository. Use can specify local template name or full repo
    # spec.
    template_source = get_template_source(module)
    provider = template_source.provider()

    # Load vars to be passed to the template
    template_vars = get_template_vars(module)

    # Ugly hack alert. Injecting template commit information to vars.deploy() object here
    set_deploy_info(template_source, provider, template_vars)

    # Load the template, passing standard and custom helpers
    config = get_config(module, template_vars)
    tpl = build_template(module, provider, config)

    if action == "render":
        # Render the template with the loaded values
        rendered = tpl.render(template_vars)
        result["content"] = str(rendered)
        if rendered.error:
            result["error"] = str(rendered.error)
            return module.fail_json(msg="Error rendering template", **result)

        result["capabilities"] = rendered.iam_capabilities()

        result["diff"] = template_diff(config, rendered)

        return module.exit_json(**result)
    else:
        result["error"] = f"Unknown action {action}"
        module.fail_json(msg=f"Unknown action {action}", **result)


def template_diff(config: MinimalConfig, rendered: RenderedTemplate):
    """return diff of rendered template vs currently deployed stack"""
    stack = Stack(aws=config.aws, name=config.vars["stack_name"])
    if stack.exists():
        diff = stack.diff(rendered)
        # remove occurrences of '[.*]' from diff string (color codes)
        diff = re.sub(r"\[[^]]+\]", "", diff)
        return diff
    return ""


def build_template(module, provider, config):
    """Load the template, passing standard and custom helpers"""
    template_helpers = TemplateHelpers(
        provider=provider,
        bucket=config.aws.cfn_bucket,
        custom_helpers=module.params["helpers"],
        config=config,
    )
    tpl = Template(name=module.params["template"], provider=provider, helpers=template_helpers)

    return tpl


def get_template_vars(module):
    """Load template vars from file and/or module parameter 'vars'"""
    template_vars = {}
    if "vars_file" in module.params and module.params["vars_file"]:
        with open(module.params["vars_file"], "r", encoding="utf-8") as f:
            template_vars = yaml.load(f, Loader=yaml.FullLoader)

    if "vars" in module.params and module.params["vars"]:
        template_vars.update(module.params["vars"])
    return template_vars


def get_config(module, template_vars):
    """
    Load config; mostly we're after aws settings which are optionally loaded from module parameter 'aws'
    """
    if "aws" in module.params and module.params["aws"]:
        aws_settings = AwsSettings(**module.params["aws"])
    else:
        aws_settings = AwsSettings(region="Not specified", cfn_bucket="Not specified")

    if "tags" in module.params and module.params["tags"]:
        tags = module.params["tags"]
    else:
        tags = {}

    return MinimalConfig(aws=aws_settings, tags=tags, template_vars=template_vars)


def set_deploy_info(template_source, provider, template_vars):
    """Add deploy information to template vars"""
    try:
        template_vars["deploy"] = Config.DeployMetadata(config_path=os.path.curdir, template_source=template_source)
        deploy = template_vars["deploy"]
        deploy.deployed_with = "ansible"

        head = provider.head()  # pylint: disable=assignment-from-none
        if head:
            deploy.template_sha = str(head.hexsha)
            deploy.template_ref = str(provider.git_ref)
    except Exception:  # pylint: disable=broad-except
        pass


def get_template_source(module):
    """
    Extract template source from module parameter 'template'; either a local file or a git repo
    """
    source = yaml.safe_load(module.params["template"])
    if isinstance(source, str):
        source = {"root": ".", "name": source}

    return TemplateSource(**source)


def main():
    """main entrypoint for Ansible module"""
    run_module()


if __name__ == "__main__":
    main()
