#!/bin/sh
# We must set the cgroup-root argument for the kubelet when using cgroupsv2, as otherwise, the parent kubelet will fight
# the child kubelet and pods will never be started properly
root_cgroup_raw=$(cat /proc/1/cgroup)
root_cgroup_stripped="${root_cgroup_raw#0::}"
root_cgroup=$(dirname "$root_cgroup_stripped")

mkdir -p /etc/rancher/rke2/config.yaml.d
mkdir -p /etc/rancher/k3s/config.yaml.d

echo "kubelet-arg+: \"cgroup-root=$root_cgroup\"" > /etc/rancher/rke2/config.yaml.d/49-cgroups-v2-kubelet-root.yaml
echo "kubelet-arg+: \"cgroup-root=$root_cgroup\"" > /etc/rancher/k3s/config.yaml.d/49-cgroups-v2-kubelet-root.yaml