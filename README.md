# Ansible Collection - stk.cloudformation

Create test project:

```bash
mkdir test-project
cd test-project
git init .
```

create a requirements file:

```yaml
# requirements.yml
---
collections:
  - name: amazon.aws
  - name: stk.cloudformation
    scm: https://github.com/jwoffindin/stk-ansible.git
```

Install requirements

```bash
ansible-galaxy collection install -r requirements.yml
```

create a sample playbook:

```yaml
# deploy-playbook.yml
---
- hosts: localhost
  name: parse template
  tasks:
    - stk.cloudformation.template:
        name: parse template
        action: render
        aws:
          cfn_bucket: TODO
          region: us-east-1
        template: ./templates/template.yaml
        vars:
          foo: "bar"
        register: template
    - debug:
        msg: "{{ template.content }}"
```

run with:

```bash
ansible-playbook ./deploy-playbook.yml

```

running this, you should see the CloudFormation template being rendered, and the last line of output should be:

```bash
localhost                  : ok=3    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

which isn't very exciting, but the template has rendered and is available in the `template.content` variable, which you can use with standard cloudformation module - as `template_body`.
