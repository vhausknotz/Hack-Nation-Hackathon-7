// The always-running atlas engine: one small Linux VM, no inbound access at all.
// Owner-approved 2026-10-04 with a total project ceiling of $45/month (VM ~$28.40, IP ~$3.65, disk ~$2.40).
// Managed through Azure Run Command; outbound only (cloud intake, OpenAI, PubMed, ClinicalTrials.gov).
targetScope = 'resourceGroup'

param location string = 'swedencentral'
param vmName string = 'atlas-engine'
param vmSize string = 'Standard_B2als_v2'
param adminUsername string = 'atlas'
@description('Emergency SSH public key; inbound SSH is blocked by the NSG, so it is only usable after an explicit rule change.')
param sshPublicKey string

var tags = { project: 'rare-disease-atlas', role: 'engine' }

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${vmName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'deny-all-inbound-internet'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${vmName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.40.0.0/24'] }
    subnets: [{ name: 'engine', properties: { addressPrefix: '10.40.0.0/27', networkSecurityGroup: { id: nsg.id } } }]
  }
}

// Outbound internet for the VM (new virtual networks have no default outbound access).
resource ip 'Microsoft.Network/publicIPAddresses@2023-11-01' = {
  name: '${vmName}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource nic 'Microsoft.Network/networkInterfaces@2023-11-01' = {
  name: '${vmName}-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig'
        properties: {
          subnet: { id: vnet.properties.subnets[0].id }
          publicIPAddress: { id: ip.id }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-03-01' = {
  name: vmName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey }] }
      }
    }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: 'ubuntu-24_04-lts', sku: 'server', version: 'latest' }
      osDisk: { createOption: 'FromImage', diskSizeGB: 32, managedDisk: { storageAccountType: 'StandardSSD_LRS' }, deleteOption: 'Delete' }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id, properties: { deleteOption: 'Delete' } }] }
    diagnosticsProfile: { bootDiagnostics: { enabled: false } }
  }
}

output vmId string = vm.id
output principalId string = vm.identity.principalId
