import errno
import os
from os import path

from django.conf import settings

from cyder.base.utils import (
    build_sanity_check, check_stop_file, copy_tree, handle_failure, mutex,
    remove_dir_contents, run_command, transaction_atomic, UnixLogger)
from cyder.core.ctnr.models import Ctnr
from cyder.cydhcp.network.models import Network
from cyder.cydhcp.vrf.models import Vrf
from cyder.cydhcp.workgroup.models import Workgroup


def check_syntax(ip_type, filepath, logger):
    out, err, ret = run_command("{} -{} -t -cf {}".format(
        settings.DHCPBUILD['dhcpd'], ip_type, filepath))

    if ret != 0:
        logger.error(
            "{} has a syntax error.\n"
            "{} said:\n"
            "{}".format(
                filepath, settings.DHCPBUILD['dhcpd'], err)
        )


@transaction_atomic
def dhcp_build(dry_run=False, sanity_check=True, verbosity=0,
        log_syslog=False):
    l = UnixLogger(to_syslog=log_syslog, verbosity=verbosity)

    with handle_failure(
                msg="Cyder DHCP build failed", logger=l,
                stop_file=settings.DHCPBUILD['stop_file']), \
            mutex(
                lock_file=settings.DHCPBUILD['lock_file'],
                pid_file=settings.DHCPBUILD['pid_file'], logger=l):
        check_stop_file(
            action_name="Cyder DHCP build", logger=l,
            filename=settings.DHCPBUILD['stop_file'],
            interval=settings.DHCPBUILD['stop_file_email_interval'])

        stage_dir = settings.DHCPBUILD['stage_dir']
        prod_dir = settings.DHCPBUILD['prod_dir']
        files_v4 = settings.DHCPBUILD['files_v4']
        files_v6 = settings.DHCPBUILD['files_v6']

        remove_dir_contents(stage_dir)
        copy_tree(prod_dir, stage_dir)

        for ip_type, files in (('4', files_v4), ('6', files_v6)):
            l.log_info('Building v{}...'.format(ip_type))
            with open(os.path.join(stage_dir, files['target_file']),
                      'w') as f:
                for ctnr in Ctnr.objects.all():
                    f.write(ctnr.build_legacy_classes(ip_type))
                for vrf in Vrf.objects.all():
                    f.write(vrf.build_vrf(ip_type))
                for network in Network.objects.filter(
                        ip_type=ip_type, enabled=True):
                    f.write(network.build_subnet())
                for workgroup in Workgroup.objects.all():
                    f.write(workgroup.build_workgroup(ip_type))

            if files['check_file']:
                check_syntax(
                    ip_type=ip_type,
                    filepath=path.join(stage_dir, files['check_file']),
                    logger=l)

        size_diff = 0
        to_stat = (
            settings.DHCPBUILD['files_v4']['target_file'],
            settings.DHCPBUILD['files_v6']['target_file'])
        for name in to_stat:
            try:
                old = os.stat(path.join(prod_dir, name)).st_size
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
                old = 0
            new = os.stat(path.join(stage_dir, name)).st_size
            size_diff += new - old

        l.log_notice('prod size - stage size = {}'.format(size_diff))

        # Do sanity check.

        if sanity_check:
            build_sanity_check(
                size_diff, settings.DHCPBUILD['size_increase_limit'],
                settings.DHCPBUILD['size_decrease_limit'])

        # Sync to prod directory if requested.

        if dry_run:
            l.log_notice("Not touching production directory")
        else:
            l.log_notice("Syncing to production directory...")
            copy_tree(stage_dir, prod_dir)

        l.log_info('DHCP build successful')

        return {
            'size_diff': size_diff,
        }
