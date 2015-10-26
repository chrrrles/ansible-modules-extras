#!/usr/bin/python
# -*- coding: utf-8 -*-

try:
  from pyVmomi import vim, vmodl
  HAS_PYVMOMI = True
except ImportError:
  HAS_PYVMOMI = False

def get_obj(content, vimtype, name=None):
  for obj in get_all_objs(content, vimtype):
    if not name:
      return obj
    if obj.name == name:  
      return obj

def create_vm(module):
  content = module.params['content']
  vm_dc = module.params['vm_dc'])
  vm_name = module.params['vm_name']
  vm_folder = module.params['vm_folder']
  ds_path = "[%s] %s" % (modul.params['vm_ds'], vm_name)
  cluster = get_obj(content, [vim.ClusterComputeResource], module.params['vm_cluster']) 
  vm_pool = module.params['vm_pool']
  files = vim.vm.FileInfo(logDirectory=None 
                          snapshotDirectory=None,
                          suspendDirectory=None,
                          vmPathName=ds_path)
  config = vim.vm.ConfigSpec(
    name = module.params['vm_name'], 
    memoryMB = module.params['vm_memoryMB'],
    numCPUs = module.params['vm_numCPUs'],
    files = files)
     
  task = folder.CreateVM_Task(config=config, pool=pool) 
  changed, result = wait_for_task(task)
  module.exit_json(changed=changed, result=str(result))

def clone_vm(module):
  content = module.params['content']
  template = find_obj(content, [vim.VirtualMachine], module.params['vm_template'])
  vm_dc = module.params['vm_dc']
  vm_pool = module.params['vm_pool']
  vm_cluster = module.params['vm_cluster']
  if module.params['vm_ds']:
    vm_ds = find_obj(content, [vim.Datastore], module.params['vm_ds'])
  else:
    vm_ds = find_obj(content, [vim.Datastore], template.datastore[0].info.name)
  vm_folder = module.params['vm_folder']
  vm_name = module.params['vm_name']
  vm_spec = module.params['vm_spec']

  # set our relospec
  relospec = vim.vm.RelocateSpec()
  relospec.datastore = vm_ds
  relospec.pool = vm_pool

  clonespec = vim.vm.CloneSpec()
  clonespec.location = relospec
  clonespec.powerOn = module.params['vm_power'] 

  task = template.Clone(folder=vm_folder, name=vm_name, spec=clonespec)
  changed, result = wait_for_task(task)
  module.exit_json(changed=changed, result=str(result))

def check_vm_state(module):
  content = connect_to_api(module)
  module.params['content'] = content
  vm = find_obj(content, [vim.VirtualMachine], module.params['vm_name'])
  if vm is None:
    return 'absent'
  module.params['vm'] = vm
  return 'present'

def state_destroy(module):
  vm = module.params['vm']
  # only destroy if 'force' is True
  if force:
    # first power down the VM
    if module.check_mode:
      module.exit_json(True, None)
    if format(vm.runtime.powerState) == "poweredOn":  
      task = vm.powerOffVM_Task()
      changed, result = wait_for_task (task)
    task = vm.destroy_task()
    changed, result =  wait_for_task(task)
    module.exit_json(changed=changed, result=str(result))

def state_create(module):
  if module.check_mode: # exit here!
    module.exit_json(True, None)
  content = module.params['content']
  module.params['vm_dc'] = find_obj(content, [vim.Datacenter], module.params['vm_dc'])
  module.params['vm_cluster'] = find_obj(content, [vim.ClusterComputeResource], module.params['vm_cluster'])
  if module.params['vm_pool']:
    module.params['vm_pool'] = find_obj(content, [vim.ResourcePool], module.params['vm_pool'])
  else: # if not specified, use the cluster's resource pool
    module.params['vm_pool'] = module.params['vm_cluster'].resourcePool
  if module.params['vm_folder']:
    module.params['vm_folder'] = find_obj(content, [vim.Folder], module.params['vm_folder'])
  else:
    module.params['vm_folder'] = module.params['vm_dc'].vmFolder

  if module.params['vm_template']:
    return clone_vm(module)
  else:
    return create_vm(module) 

def state_stopped(module):
  if module.check_mode:
    module.exit_json(True, None)
  content = module.params['content']
  vm = module.params['vm']
  task = vm.powerOffVM_Task()
  changed, result = wait_for_task(task)
  module.exit_json(changed=changed, result=str(result))

def state_maintenance(module):
  pass

def state_restarted(module):
  pass

def state_absent(module):
  module.fail_json(msg="Attempting operation on non-existent VM")

def state_exit(module):
  module.exit_json(changed=False)

def main():
  argument_spec = vmware_argument_spec()
  argument_spec.update(dict(
    state = dict(default='present', choices=['present', 'absent', 'stopped', 'maintenance'], type='str'),
    force = dict(default=False, type='bool'),
    vm_dc = dict(default=None, type='str'),
    vm_pool = dict(default=None, type='str'),
    vm_cluster = dict(default=None, type='str'),
    vm_ds = dict(default=None, type='str'),
    vm_folder = dict(default=None, type='str'),
    vm_template = dict(default=None, type='str'),
    vm_name = dict(required=True, type='str'), 
    vm_power = dict(default=True, type='bool'),
    vm_memoryMB = dict(default=None, type='dict')
    vm_numCPUs = dict(default=None, type='dict')
    ))
  
  module = AnsibleModule(argument_spec=argument_spec)
  if not HAS_PYVMOMI:
    module.fail_json(msg='pyvmomi is required for this module')

  vm_states = {
    'absent': {
      'present': state_destroy,
      'maintenance': state_destroy,
      'stopped': state_destroy,
      'absent': state_exit },
    'present': {
      'present': state_exit,
      'maintenance': state_exit,
      'stopped': state_exit,
      'absent': state_create },
    'maintenance': {
      'present': state_maintenance,
      'maintenance': state_exit,
      'stopped': state_maintenance,
      'absent': state_absent }
    'stopped': {
      'present': state_stoppped,
      'maintenance': state_stopped,
      'stopped': state_exit,
      'absent': state_absent },
    'restarted': {
      'present': state_restarted,
      'maintenance': state_restarted,
      'stopped': state_restarted,
      'absent': state_absent }}

  desired_state = module.params['state']
  current_state = check_vm_state(module)

  try:
    vm_states[desired_state][current_state](module)
  except Exception as e:
    module.fail_json(msg=str(e))

from ansible.module_utils.vmware import *
from ansible.module_utils.basic import *

if __name__ == '__main__':
  main()
