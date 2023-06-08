# Copyright (C) 2009-2010 Canonical Ltd.
# Copyright (C) 2012, 2013 Hewlett-Packard Development Company, L.P.
# Copyright (C) 2012 Yahoo! Inc.
#
# Author: Scott Moser <scott.moser@canonical.com>
# Author: Juerg Hafliger <juerg.haefliger@hp.com>
# Author: Joshua Harlow <harlowja@yahoo-inc.com>
#
# This file is part of cloud-init. See LICENSE file for license information.
# This provider is a stripped version of the NoCloud provider here: https://github.com/canonical/cloud-init/blob/8615c240c2405165d9755b838bc2be5d82ad0c1d/cloudinit/sources/DataSourceNoCloud.py
# that does not react to external media. This is specifically to allow ignoring external media based cloud-init data that does not apply to the container (for example, lima)

import errno
import os

from cloudinit import dmi
from cloudinit import log as logging
from cloudinit import sources, util
from cloudinit.net import eni

LOG = logging.getLogger(__name__)

class DataSourceNoCloudNoMedia(sources.DataSource):

    dsname = "NoCloudNoMedia"

    def __init__(self, sys_cfg, distro, paths):
        sources.DataSource.__init__(self, sys_cfg, distro, paths)
        self.seed = None
        self.seed_dirs = [
            os.path.join(paths.seed_dir, "nocloud"),
        ]
        self.seed_dir = None
        self.supported_seed_starts = ("/", "file://")

    def __str__(self):
        root = sources.DataSource.__str__(self)
        return "%s [seed=%s][dsmode=%s]" % (root, self.seed, self.dsmode)

    def _get_data(self):
        defaults = {
            "instance-id": "nocloud",
            "dsmode": self.dsmode,
        }

        found = []
        mydata = {
            "meta-data": {},
            "user-data": "",
            "vendor-data": "",
            "network-config": None,
        }

        try:
            # Parse the system serial label from dmi. If not empty, try parsing
            # like the commandline
            md = {}
            serial = dmi.read_dmi_data("system-serial-number")
            if serial and load_cmdline_data(md, serial):
                found.append("dmi")
                mydata = _merge_new_seed(mydata, {"meta-data": md})
        except Exception:
            util.logexc(LOG, "Unable to parse dmi data")
            return False

        try:
            # Parse the kernel command line, getting data passed in
            md = {}
            if load_cmdline_data(md):
                found.append("cmdline")
                mydata = _merge_new_seed(mydata, {"meta-data": md})
        except Exception:
            util.logexc(LOG, "Unable to parse command line data")
            return False

        # Check to see if the seed dir has data.
        pp2d_kwargs = {
            "required": ["user-data", "meta-data"],
            "optional": ["vendor-data", "network-config"],
        }

        for path in self.seed_dirs:
            try:
                seeded = util.pathprefix2dict(path, **pp2d_kwargs)
                found.append(path)
                LOG.debug("Using seeded data from %s", path)
                mydata = _merge_new_seed(mydata, seeded)
                break
            except ValueError:
                pass

        # If the datasource config had a 'seedfrom' entry, then that takes
        # precedence over a 'seedfrom' that was found in a filesystem
        # but not over external media
        if self.ds_cfg.get("seedfrom"):
            found.append("ds_config_seedfrom")
            mydata["meta-data"]["seedfrom"] = self.ds_cfg["seedfrom"]

        # fields appropriately named can also just come from the datasource
        # config (ie, 'user-data', 'meta-data', 'vendor-data' there)
        if "user-data" in self.ds_cfg and "meta-data" in self.ds_cfg:
            mydata = _merge_new_seed(mydata, self.ds_cfg)
            found.append("ds_config")

        def _pp2d_callback(mp, data):
            return util.pathprefix2dict(mp, **data)

        # There was no indication on kernel cmdline or data
        # in the seeddir suggesting this handler should be used.
        if len(found) == 0:
            return False

        # The special argument "seedfrom" indicates we should
        # attempt to seed the userdata / metadata from its value
        # its primarily value is in allowing the user to type less
        # on the command line, ie: ds=nocloud;s=http://bit.ly/abcdefg/
        if "seedfrom" in mydata["meta-data"]:
            seedfrom = mydata["meta-data"]["seedfrom"]
            seedfound = False
            for proto in self.supported_seed_starts:
                if seedfrom.startswith(proto):
                    seedfound = proto
                    break
            if not seedfound:
                LOG.debug("Seed from %s not supported by %s", seedfrom, self)
                return False
            # check and replace instances of known dmi.<dmi_keys> such as
            # chassis-serial-number or baseboard-product-name
            seedfrom = dmi.sub_dmi_vars(seedfrom)

            # This could throw errors, but the user told us to do it
            # so if errors are raised, let them raise
            (md_seed, ud, vd) = util.read_seeded(seedfrom, timeout=None)
            LOG.debug("Using seeded cache data from %s", seedfrom)

            # Values in the command line override those from the seed
            mydata["meta-data"] = util.mergemanydict(
                [mydata["meta-data"], md_seed]
            )
            mydata["user-data"] = ud
            mydata["vendor-data"] = vd
            found.append(seedfrom)

        # Now that we have exhausted any other places merge in the defaults
        mydata["meta-data"] = util.mergemanydict(
            [mydata["meta-data"], defaults]
        )

        self.dsmode = self._determine_dsmode(
            [mydata["meta-data"].get("dsmode")]
        )

        if self.dsmode == sources.DSMODE_DISABLED:
            LOG.debug(
                "%s: not claiming datasource, dsmode=%s", self, self.dsmode
            )
            return False

        self.seed = ",".join(found)
        self.metadata = mydata["meta-data"]
        self.userdata_raw = mydata["user-data"]
        self.vendordata_raw = mydata["vendor-data"]
        self._network_config = mydata["network-config"]
        self._network_eni = mydata["meta-data"].get("network-interfaces")
        return True

    @property
    def platform_type(self):
        # Handle upgrade path of pickled ds
        if not hasattr(self, "_platform_type"):
            self._platform_type = None
        if not self._platform_type:
            self._platform_type = "lxd" if util.is_lxd() else "nocloudnomedia"
        return self._platform_type

    def _get_cloud_name(self):
        """Return unknown when 'cloud-name' key is absent from metadata."""
        return sources.METADATA_UNKNOWN

    def _get_subplatform(self):
        """Return the subplatform metadata source details."""
        if self.seed.startswith("/dev"):
            subplatform_type = "config-disk"
        else:
            subplatform_type = "seed-dir"
        return "%s (%s)" % (subplatform_type, self.seed)

    def check_instance_id(self, sys_cfg):
        # quickly (local check only) if self.instance_id is still valid
        # we check kernel command line or files.
        current = self.get_instance_id()
        if not current:
            return None

        # LP: #1568150 need getattr in the case that an old class object
        # has been loaded from a pickled file and now executing new source.
        dirs = getattr(self, "seed_dirs", [self.seed_dir])
        quick_id = _quick_read_instance_id(dirs=dirs)
        if not quick_id:
            return None
        return quick_id == current

    @property
    def network_config(self):
        if self._network_config is None:
            if self._network_eni is not None:
                self._network_config = eni.convert_eni_data(self._network_eni)
        return self._network_config


def _quick_read_instance_id(dirs=None):
    if dirs is None:
        dirs = []

    iid_key = "instance-id"
    fill = {}
    if load_cmdline_data(fill) and iid_key in fill:
        return fill[iid_key]

    for d in dirs:
        if d is None:
            continue
        try:
            data = util.pathprefix2dict(d, required=["meta-data"])
            md = util.load_yaml(data["meta-data"])
            if md and iid_key in md:
                return md[iid_key]
        except ValueError:
            pass

    return None


def load_cmdline_data(fill, cmdline=None):
    pairs = [
        ("ds=nocloudnomedia", sources.DSMODE_LOCAL),
    ]
    for idstr, dsmode in pairs:
        if not parse_cmdline_data(idstr, fill, cmdline):
            continue
        if "dsmode" in fill:
            # if dsmode was explicitly in the command line, then
            # prefer it to the dsmode based on seedfrom type
            return True

        seedfrom = fill.get("seedfrom")
        if seedfrom:
            if seedfrom.startswith(("file://", "/")):
                fill["dsmode"] = sources.DSMODE_LOCAL
        else:
            fill["dsmode"] = dsmode

        return True
    return False


# Returns true or false indicating if cmdline indicated
# that this module should be used.  Updates dictionary 'fill'
# with data that was found.
# Example cmdline:
#  root=LABEL=uec-rootfs ro ds=nocloud
def parse_cmdline_data(ds_id, fill, cmdline=None):
    if cmdline is None:
        cmdline = util.get_cmdline()
    cmdline = " %s " % cmdline

    if not (" %s " % ds_id in cmdline or " %s;" % ds_id in cmdline):
        return False

    argline = ""
    # cmdline can contain:
    # ds=nocloud[;key=val;key=val]
    for tok in cmdline.split():
        if tok.startswith(ds_id):
            argline = tok.split("=", 1)

    # argline array is now 'nocloud' followed optionally by
    # a ';' and then key=value pairs also terminated with ';'
    tmp = argline[1].split(";")
    if len(tmp) > 1:
        kvpairs = tmp[1:]
    else:
        kvpairs = ()

    # short2long mapping to save cmdline typing
    s2l = {"h": "local-hostname", "i": "instance-id", "s": "seedfrom"}
    for item in kvpairs:
        if item == "":
            continue
        try:
            (k, v) = item.split("=", 1)
        except Exception:
            k = item
            v = None
        if k in s2l:
            k = s2l[k]
        fill[k] = v

    return True


def _merge_new_seed(cur, seeded):
    ret = cur.copy()

    newmd = seeded.get("meta-data", {})
    if not isinstance(seeded["meta-data"], dict):
        newmd = util.load_yaml(seeded["meta-data"])
    ret["meta-data"] = util.mergemanydict([cur["meta-data"], newmd])

    if seeded.get("network-config"):
        ret["network-config"] = util.load_yaml(seeded.get("network-config"))

    if "user-data" in seeded:
        ret["user-data"] = seeded["user-data"]
    if "vendor-data" in seeded:
        ret["vendor-data"] = seeded["vendor-data"]
    return ret


# Used to match classes to dependencies
datasources = [
    (DataSourceNoCloudNoMedia, (sources.DEP_FILESYSTEM,)),
]

# Return a list of data sources that match this set of dependencies
def get_datasource_list(depends):
    return sources.list_from_depends(depends, datasources)

