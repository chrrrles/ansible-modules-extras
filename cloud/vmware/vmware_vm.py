#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: vmware_vm
short_description: Manage VMware vSphere Virtual Machines
description:
    - Manage VMware vSphere Virtual Machines
version_added: 2.0
author: "Charles Paul (@chrrrles)"
notes:
  - Tested on vSphere 6.0
requirements:
    - "python >= 2.6"
    - PyVmomi
options:
    hostname:
        description:
            - The hostname or IP address of the vSphere vCenter API server
        required: True
    username:
        description:
            - The username of the vSphere vCenter
        required: True
        aliases: ['user', 'admin']
    password:
        description:
            - The password of the vSphere vCenter
        required: True
        aliases: ['pass', 'pwd']
    vm_name:
        description:
            - The name of the VM.
        required: True
    vm_datacenter:
        description:
            - The name of the datacenter for the VM.
        required: False
    vm_pool:
        description:
            - The name of the resource pool for the VM.
        required: False
    vm_cluster:
        description:
            - The name of the cluster for the VM.
        required: False
    vm_datastore:
        description:
            - The name of the datastore for the VM.
        required: False
    vm_folder:
        description:
            - The name of the folder for the VM.
        required: False
    vm_template:
        description:
            - The name of the template used for the VM.
        required: False
    vm_power:
        description:
            - The power on state for the VM
        default: "yes"
        choices: ["yes", "no"]
    vm_memoryMB:
        description:
            - Integer for the amount of memory (in MB) to provision for the VM
        required: False
    vm_numCPUs:
        description:
            - Integer for the number of CPUs to provision for the VM
        required: False
    vm_guest_id:
        description:
            - The guestId string to use for the VM
        default: "otherLinuxGuest"
    vm_nic_type:
        description:
            - The network card type to use for the VM
        choices: ['vmxnet', 'vmxnet3', 'e1000', 'e1000e']
    vm_network
        description:
            - The name of the network to use for the VM
        default: "VM Network"
    state:
        description:
            - If the datacenter should be present or absent
        choices: ['present', 'absent']
        required: True
'''

EXAMPLES = '''
- name: Destroy VM
      local_action: >
        vmware_vm
        hostname=10.1.1.2
        username=root 
        password=vmware
        vm_name=test-vm
- name: Create VM
      local_action: >
        vmware_vm
        hostname=10.1.1.2
        username=root 
        password=vmware
        vm_name=test-vm
        vm_datacenter=Datacenter1
        vm_datastore=test-volume
        vm_pool=Testing
        vm_name=test-vm
        vm_memoryMB=2048
        vm_numCPUs=2
        vm_power=false
'''

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
  vm_datacenter = module.params['vm_datacenter']
  vm_name = module.params['vm_name']
  vm_folder = module.params['vm_folder']
  ds_path = "[%s] %s" % (module.params['vm_datastore'], vm_name)
  cluster = module.params['vm_cluster'] 
  vm_pool = module.params['vm_pool']

  # [XXX] Only one network for now
  vm_network = module.params['vm_network']
  vm_nic_type = module.params['vm_nic_type']
  if vm_nic_type == 'vmxnet':
    nic_device = vim.vm.device.VirtualVmxnet
  elif vm_nic_type == 'e1000e':
    nic_device = vim.vm.device.VirtualE1000e
  elif vm_nic_type == 'e1000':
    nic_device = vim.vm.device.VirtualE1000
  elif vm_nic_type == 'vmxnet2':
    nic_device = vim.vm.device.VirtualVmxnet2
  else: # we assume vmxnet3 for better compatibility
    nic_device = vim.vm.device.VirtualVmxnet3
  nic_spec = vim.vm.device.VirtualDeviceSpec(
    operation = vim.vm.device.VirtualDeviceSpec.Operation.add,
    device = nic_device(
      backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo(
        network=get_obj(content, [vim.Network], vm_network),
        deviceName=vm_network),
      connectable = vim.vm.device.VirtualDevice.ConnectInfo(
        startConnected=True,
        allowGuestControl=True)
    )
  )

  files = vim.vm.FileInfo(logDirectory=None,
                          snapshotDirectory=None,
                          suspendDirectory=None,
                          vmPathName=ds_path)
  config = vim.vm.ConfigSpec(
    name = vm_name,
    memoryMB = module.params['vm_memoryMB'],
    numCPUs = module.params['vm_numCPUs'],
    files = files,
    guestId = module.params['vm_guest_id'],
    deviceChange=[nic_spec])

  task = vm_folder.CreateVM_Task(config=config, pool=vm_pool) 
  changed, result = wait_for_task(task)
  if module.params['vm_power']:
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    task = vm.PowerOn()
    changed, result = wait_for_task(task)
  module.exit_json(changed=changed, result=str(result))

def clone_vm(module):
  content = module.params['content']
  template = get_obj(content, [vim.VirtualMachine], module.params['vm_template'])
  vm_datacenter = module.params['vm_datacenter']
  vm_pool = module.params['vm_pool']
  vm_cluster = module.params['vm_cluster']
  if module.params['vm_datastore']:
    vm_datastore = get_obj(content, [vim.Datastore], module.params['vm_datastore'])
  else:
    vm_datastore = get_obj(content, [vim.Datastore], template.datastore[0].info.name)
  vm_folder = module.params['vm_folder']
  vm_name = module.params['vm_name']
  vm_spec = module.params['vm_spec']

  # set our relospec
  relospec = vim.vm.RelocateSpec()
  relospec.datastore = vm_datastore
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
  vm = get_obj(content, [vim.VirtualMachine], module.params['vm_name'])
  if vm is None:
    return 'absent'
  module.params['vm'] = vm
  return 'present'

def state_destroy(module):
  vm = module.params['vm']
  # first power down the VM
  if module.check_mode:
    module.exit_json(True, None)
  if format(vm.runtime.powerState) == "poweredOn":  
    task = vm.PowerOffVM_Task()
    changed, result = wait_for_task (task)
  task = vm.Destroy_Task()
  changed, result =  wait_for_task(task)
  module.exit_json(changed=changed, result=str(result))

def state_create(module):
  if module.check_mode: # exit here!
    module.exit_json(True, None)
  content = module.params['content']
  vm_cluster = module.params['vm_cluster']
  module.params['vm_datacenter'] = get_obj(content, [vim.Datacenter], module.params['vm_datacenter'])
  module.params['vm_cluster'] = get_obj(content, [vim.ClusterComputeResource], vm_cluster)
  if module.params['vm_pool']:
    module.params['vm_pool'] = get_obj(content, [vim.ResourcePool], module.params['vm_pool'])
  else: # if not specified, use the cluster's resource pool
    module.params['vm_pool'] = module.params['vm_cluster'].resourcePool
  if module.params['vm_folder']:
    module.params['vm_folder'] = get_obj(content, [vim.Folder], module.params['vm_folder'])
  else:
    module.params['vm_folder'] = module.params['vm_datacenter'].vmFolder

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
    # [XXX] should be this: state = dict(default='present', choices=['present', 'absent', 'stopped', 'maintenance'], type='str'),
    state = dict(default='present', choices=['present', 'absent'], type='str'),
    vm_name = dict(required=True, type='str'), 
    vm_datacenter = dict(default=None, type='str'),
    vm_pool = dict(default=None, type='str'),
    vm_cluster = dict(default=None, type='str'),
    vm_datastore = dict(default=None, type='str'),
    vm_folder = dict(default=None, type='str'),
    vm_template = dict(default=None, type='str'),
    vm_power = dict(default=True, type='bool'),
    vm_memoryMB = dict(default=None, type='int'),
    vm_numCPUs = dict(default=None, type='int'),
    vm_guest_id = dict(default='otherLinuxGuest', type='str'),
    vm_nic_type = dict(default='vmxnet3', choices=['vmxnet', 'vmxnet3', 'e1000', 'e1000e'], type='str'),
    vm_network = dict(default="VM Network", type='str')
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
      'absent': state_absent },
    'stopped': {
      'present': state_stopped,
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
