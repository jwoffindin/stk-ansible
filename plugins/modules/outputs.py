#!/usr/bin/env python

"""
This module allows retrieving of CloudFormation outputs for an
existing stack.
"""

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from stk.stack_reference import StackReference
from stk.aws_config import AwsSettings

__metaclass__ = type  # pylint: disable=invalid-name

DOCUMENTATION = r"""
---
module: outputs

short_description: Expose CloudFormation outputs as facts

version_added: "1.0.0"

options:
    stack_name:
        description: Name of stack to retrieve outputs
        required: true
        type: str
    aws:
        description: AWS settings - required if using some stk helpers (e.g. user_data)
        required: false
        type: dict
author:
    - John Woffindin
"""

EXAMPLES = r"""
# Render a template in current directory passing in single variable 'role_name'
- stack_name: "{{ environment}}-vpc"
  aws:
    region: ap-southeast-2
    cfn_bucket: None
"""

RETURN = r"""
# These are examples of possible return values, and in general should use other names for return values.
outputs:
    description: Outputs from CloudFormation stack
    type: dict
    returned: always
    sample: '....'
error:
    description: Error message if any error occurred
    type: str
    returned: sometimes
    sample: 'Stack not found'
"""


def run_module():
    """entrypoint for Ansible module"""
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        stack_name=dict(type="str", required=True),
        aws=dict(type="dict", required=False),
    )

    # seed the result dict in the object
    result = dict(changed=False, content="", error="")

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    stack = StackReference(aws_settings(module), module.params["stack_name"])

    if stack.exists():
        return module.exit_json(**stack.outputs())
    else:
        result["error"] = f"Stack {module.params['stack_name']} not found"
        return module.fail_json(msg="Error rendering template", **result)


def aws_settings(module):
    """
    Extract AWS settings from module parameter 'aws'
    """
    if "aws" in module.params and module.params["aws"]:
        aws_settings = AwsSettings(**module.params["aws"])
    else:
        aws_settings = AwsSettings(region="ap-southeast-2", cfn_bucket="None")

    return aws_settings


def main():
    """main entrypoint for Ansible module"""
    run_module()


if __name__ == "__main__":
    main()
