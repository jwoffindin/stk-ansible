#!/usr/bin/env python

"""
This module allows AWS account ID, and optional verification that we're
deploying to the correct account.
"""

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from stk.stack_reference import StackReference
from stk.aws_config import AwsSettings

__metaclass__ = type  # pylint: disable=invalid-name

DOCUMENTATION = r"""
---
module: outputs

short_description: Fetch and confirm AWS account

version_added: "1.0.0"

options:
    expected_account_id:
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
- aws:
    region: ap-southeast-2
    cfn_bucket: None
"""

RETURN = r"""
# These are examples of possible return values, and in general should use other names for return values.
id:
    description: Account ID
    type: string
    returned: always
    sample: '123456789012'
error:
    description: Error message if any error occurred
    type: str
    returned: sometimes
    sample: 'Cannot find authenticate'
"""


def run_module():
    """entrypoint for Ansible module"""
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        aws=dict(type="dict", required=False),
        expected_account_id=dict(type="str", required=False),
    )

    # seed the result dict in the object
    result = dict(changed=False, error="")

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    aws = aws_settings(module)
    try:
        account_id = aws.get_account_id()
        result["id"] = account_id
        if module.params["expected_account_id"] and module.params["expected_account_id"] != account_id:
            result["error"] = f"Expected account ID {module.params['expected_account_id']} but got {account_id}"
            return module.fail_json(msg="Account mismatch", **result)
        return module.exit_json(**result)
    except Exception as e:
        result["error"] = f"Unable to retrieve account ID: {e}, {aws}"
        return module.fail_json(msg="Client error", **result)


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
