import subprocess
import shutil
import datetime
import os
from django.core.management.base import BaseCommand, CommandError

# Resolve project root regardless of where the app is deployed
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

class Command(BaseCommand):
    help = 'Stops the background trackerjacker process and disables monitor mode.'

    def add_arguments(self, parser):
        parser.add_argument('interface', type=str, help='The monitor interface to stop (e.g., wlan1mon)')

    def handle(self, *args, **options):
        mon_iface = options['interface']

        try:
            kill_cmd = ['sudo', 'pkill', '-f', 'trackerjacker']
            subprocess.run(kill_cmd, check=True, capture_output=True)
            self.stdout.write(self.style.SUCCESS('Successfully stopped trackerjacker.'))
            
        except subprocess.CalledProcessError:
            self.stdout.write(self.style.NOTICE('No running trackerjacker process found. Moving on.'))

        try:
            airmon_cmd = ['sudo', 'airmon-ng', 'stop', mon_iface]
            subprocess.run(airmon_cmd, check=True, capture_output=True, text=True)
            self.stdout.write(self.style.SUCCESS(f'Monitor mode disabled. {mon_iface} network interface restored.'))
            
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f'Failed to stop monitor mode: {e.stderr}'))
            raise CommandError('Encountered an error while trying to stop airmon-ng.')

        wifi_map_path = os.path.join(_BASE_DIR, 'app', 'tracker', 'saves', 'wifi_map.yaml')
        try:
            if os.path.exists(wifi_map_path):
                timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                backup_path = f"{wifi_map_path}.{timestamp}.bak"
                shutil.copy2(wifi_map_path, backup_path)
                self.stdout.write(self.style.SUCCESS(f'Scan data saved: {backup_path}'))
            else:
                self.stdout.write(self.style.WARNING('No wifi_map.yaml found to save.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to save scan data: {str(e)}'))