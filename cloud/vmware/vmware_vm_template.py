#!/usr/bin/python
# -*- coding: utf-8 -*-

try:
  from pyVmomi import vim, vmodl
  HAS_PYVMOMI = True
except ImportError:
  HAS_PYVMOMI = False

def get_obj(content, vimtype, name=None): # [XXX] should place in module_utils
  for obj in get_all_objs(content, vimtype):
    if not name:
      return obj
    if obj.name == name:
      return obj

def check_template_state(module):
  content = connect_to_api(module)
  module.params['content'] = content
  source_vm = module.params['source_vm']
  template_name = module.params['template_name']
  template = get_obj(content, [vim.VirtualMachine], template_name)
  if template:
    if template.config.template:
      return 'present'
  return 'absent'

def state_destroy(module):
  content = module.params['content']
  template_name = module.params['template_name']
  template = get_obj(content, [vim.VirtualMachine],template_name)
  if template.config.template:
    task = template.Destroy_Task()
    changed, result = wait_for_task(task)
    module.exit_json(changed=changed, result=str(result))
  else:
    module.fail_json(msg="vm %s is not a template and will not be destroyed" % template_name)

def state_exit_unchanged(module):
  module.exit_json(changed=False)

def state_create(module):
  content = module.params['content']
  vm = get_obj(content, [vim.VirtualMachine], module.params['source_vm'])
  if not vm:
    module.fail_json(msg="Attempting operation on non-existent VM")
  relocate_spec = vim.vm.RelocateSpec(pool=vm.resourcePool)
  clone_spec = vim.vm.CloneSpec(powerOn=False, template=True, location=relocate_spec)

  template_name = module.params['template_name']

  if template_name:
    task = vm.CloneVM_Task(vm.parent,template_name, clone_spec)
    changed, result = wait_for_task(task)
    module.exit_json(changed=changed, result=str(result))
  else: # if no template name then we are marking the vm itself as the template
    try:
      vm.MarkAsTemplate()
      module.exit_json(changed=True, result="Created template: %s" % template_name)
    except pyVmomi.vim.MethodFault as e:
      module.fail_json(msg="Error marking vm as template: %s" % e.msg )

def main():
  argument_spec = vmware_argument_spec()
  argument_spec.update(dict(
    source_vm = dict(type='str', default=None),
    template_name = dict(type='str', default=None),
    state= dict(type='str', default='present', choices=['present', 'absent'])
    ))
  module = AnsibleModule(argument_spec=argument_spec)
  if not HAS_PYVMOMI:
    module.fail_json(msg='pyvmomi is required for this module')

  template_states = {
    'absent': {
      'present': state_destroy,
      'absent': state_exit_unchanged
    },
    'present': {
      'present': state_exit_unchanged,
      'absent': state_create
    }
  }

  desired_state = module.params['state']
  current_state= check_template_state(module)
  template_states[desired_state][current_state](module)

  try:
    create_template(module)
  except Exception as e:
    module.fail_json(msg=str(e))

from ansible.module_utils.vmware import *
from ansible.module_utils.basic import *

if __name__ == '__main__':
  main()
