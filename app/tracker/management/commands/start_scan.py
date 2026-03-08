import subprocess
import os
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Enables monitor mode and starts trackerjacker in the background directly from Django.'

    def add_arguments(self, parser):
        parser.add_argument('interface', type=str, help='The wireless interface to use (e.g., wlan1)')

    def handle(self, *args, **options):
        wifi_iface = options['interface']
        mon_iface = f'{wifi_iface}mon' 
        tracker_path = '/home/pi/AirscopeGuardian/venv/bin/trackerjacker'
        wifi_map_path = '/home/pi/AirscopeGuardian/app/tracker/saves/wifi_map.yaml'

        try:
            parent_dir = os.path.dirname(wifi_map_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                self.stdout.write(self.style.SUCCESS(f'Created directory {parent_dir} for wifi map output.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to create directory for wifi map: {str(e)}'))
            raise CommandError('Aborting scan setup due to filesystem error.')

        existing_ifaces = os.listdir('/sys/class/net/')
        if mon_iface in existing_ifaces:
            self.stdout.write(self.style.WARNING(
                f'Monitor interface {mon_iface} already exists. Skipping airmon-ng and proceeding.'
            ))
        else:
            try:
                airmon_cmd = ['sudo', 'airmon-ng', 'start', wifi_iface]
                subprocess.run(airmon_cmd, check=True, capture_output=True, text=True)
                self.stdout.write(self.style.SUCCESS(f'Monitor mode enabled successfully on {wifi_iface}.'))

            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f'Failed to start monitor mode: {e.stderr}'))
                raise CommandError('Aborting scan setup due to airmon-ng failure.')

        try:
            with open(wifi_map_path, 'w') as f:
                f.write('---\n')
            self.stdout.write(self.style.SUCCESS(f'Cleared {wifi_map_path} for new scan.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to clear {wifi_map_path}: {str(e)}'))
            raise CommandError('Aborting scan setup due to wifi_map.yaml preparation failure.')

        try:
            tracker_cmd = [
                '/home/pi/AirscopeGuardian/venv/bin/python',
                tracker_path,
                '--map',
                '--map-file', wifi_map_path,
                '-i', mon_iface
            ]

            process = subprocess.Popen(
                tracker_cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Success! Trackerjacker is now running in the background (PID: {process.pid}) on {mon_iface}. '
                f'It is mapping devices to {wifi_map_path}.'
            ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An error occurred while starting trackerjacker: {str(e)}'))
            raise CommandError('Failed to start trackerjacker.')