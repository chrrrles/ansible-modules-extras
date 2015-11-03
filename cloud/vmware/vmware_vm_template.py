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


def create_template(module):
  content = connect_to_api(module)
  vm = get_obj(content, [vim.VirtualMachine], module.params['vm_name'])
  if not vm:
    module.fail_json(msg="Attempting operation on non-existent VM")
  relospec = vim.vm.RelocateSpec()
  clonespec = vim.vm.CloneSpec()
  clonespec.location = relospec

  template_name = module.params['template_name']

  if template_name:
    task = vm.CloneVM_Task(vm.parent,template_name, clonespec)
    changed, result = wait_for_task(task)
    module.exit_json(changed=changed, result=str(result))
  else: # if no template name then we are marking the vm itself as the template
    try:
      vm.MarkAsTemplate()
    except pyVmomi.vim.MethodFault as e:
      module.fail_json(msg="Error marking vm as template: %s" % e.msg )

def main():
  argument_spec = vmware_argument_spec()
  argument_spec.update(dict(
    vm_name = dict(type='str', required=True),
    template_name = dict(type='str', default=None),
    ))
  module = AnsibleModule(argument_spec=argument_spec)
  if not HAS_PYVMOMI:
    module.fail_json(msg='pyvmomi is required for this module')
  try:
    create_template(module)
  except Exception as e:
    module.fail_json(msg=str(e))

from ansible.module_utils.vmware import *
from ansible.module_utils.basic import *

if __name__ == '__main__':
  main()
