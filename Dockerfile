FROM opensuse/leap:15.4
RUN zypper mr --disable repo-non-oss repo-update-non-oss && \
    zypper mr --no-refresh repo-oss && \
    zypper ref repo-oss repo-update
RUN zypper in -y systemd openssh cloud-init vim less jq curl tar gzip

# Kubernetes deps
RUN zypper in -y iptables

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
 
# Add k9s
RUN curl -fL https://github.com/derailed/k9s/releases/download/v0.26.3/k9s_Linux_x86_64.tar.gz | tar xvzf - -C /usr/bin k9s

# Dummy services
COPY noop.service noop.target /etc/systemd/system/
COPY 10_datasource.cfg /etc/cloud/cloud.cfg.d/
COPY default_userdata /var/lib/cloud/seed/nocloud/user-data
COPY env /etc/bash.bashrc.local
RUN touch /var/lib/cloud/seed/nocloud/meta-data /etc/fstab

VOLUME /var/lib/kubelet
VOLUME /var/lib/rancher
CMD ["/usr/lib/systemd/systemd", "--unit=noop.target", "--show-status=true"]
