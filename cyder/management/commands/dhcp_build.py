import syslog
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from cyder.cydhcp.build.build import dhcp_build


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        ### action options ###
        make_option('-n', '--dry-run',
                    dest='dry_run',
                    action='store_true',
                    default=False,
                    help="Don't sync to production directory."),
        ### logging/debug options ###
        make_option('-l', '--syslog',
                    dest='log_syslog',
                    action='store_true',
                    help="Log to syslog."),
        make_option('-L', '--no-syslog',
                    dest='log_syslog',
                    action='store_false',
                    help="Do not log to syslog."),
        ### miscellaneous ###
        make_option('-C', '--no-sanity-check',
                    dest='sanity_check',
                    action='store_false',
                    default=True,
                    help="Don't run the diff sanity check."),
    )

    def handle(self, *args, **options):
        if options['log_syslog'] is None:
            options['log_syslog'] = settings.DHCPBUILD['log_syslog']

        if options['log_syslog']:
            syslog.openlog('dhcp_build', facility=syslog.LOG_LOCAL6)

        dhcp_build(
            dry_run=options['dry_run'],
            sanity_check=options['sanity_check'],
            verbosity=int(options['verbosity']),
            log_syslog=options['log_syslog'],
        )
