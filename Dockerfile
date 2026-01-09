FROM opensuse/leap:16.0
RUN echo "solver.allowVendorChange = true" >> /etc/zypp/zypp.conf && \
    zypper mr --disable openSUSE:repo-non-oss openSUSE:repo-openh264 && \
    zypper mr --no-refresh openSUSE:repo-oss && \
    zypper ar https://download.opensuse.org/repositories/security:SELinux/16.0/security:SELinux.repo && \
    zypper --gpg-auto-import-keys --non-interactive ref openSUSE:repo-oss security_SELinux
RUN zypper in -y systemd openssh cloud-init vim less jq curl tar gzip iptables util-linux-systemd

ENV container=docker

# Disable all services
RUN for i in /usr/lib/systemd/system/*.service; do systemctl mask $(basename $i); done

# Renable some all services
RUN cd /etc/systemd/system/ && \
    rm -f \
        systemd-journald.service \
        rc-local.service \
        systemd-exit.service \
        sshd.service \
        cloud-init-local.service \
        cloud-init.service \
        cloud-config.service \
        cloud-final.service

COPY prepare-cgroups-v2.sh /
RUN chmod +x /prepare-cgroups-v2.sh

# Dummy services
COPY noop.service noop.target extra-mounts.service /etc/systemd/system/
COPY DataSourceNoCloudNoMedia.py /usr/lib/python3.13/site-packages/cloudinit/sources/
COPY 10_datasource.cfg /etc/cloud/cloud.cfg.d/
COPY default_userdata /var/lib/cloud/seed/nocloud/user-data
COPY env /etc/bash.bashrc.local
RUN touch /var/lib/cloud/seed/nocloud/meta-data /etc/fstab

COPY default_env /etc/default/rke2-server
COPY default_env /etc/default/rke2-agent
COPY default_env /etc/default/k3s
COPY default_env /etc/default/k3s-agent
COPY default_env /etc/default/rancher-system-agent

VOLUME /var/lib/kubelet
VOLUME /var/lib/rancher
CMD ["/usr/lib/systemd/systemd", "--unit=noop.target", "--show-status=true"]
