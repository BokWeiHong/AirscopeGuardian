from django.db import models
from django.utils import timezone

class Asset(models.Model):
    """
    Represents the continuous, current state of any physical device in the airspace.
    Merges both Access Points and Clients into a single normalized table.
    """
    ASSET_TYPES = [
        ('AP', 'Access Point'),
        ('CLIENT', 'Client Device'),
        ('UNKNOWN', 'Unknown RF Source'),
    ]

    # Core Identity
    mac_address = models.CharField(max_length=17, unique=True, db_index=True)
    vendor_oui = models.CharField(max_length=100, null=True, blank=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES, default='UNKNOWN', db_index=True)
    
    # Network Characteristics
    ssid_alias = models.CharField(max_length=255, null=True, blank=True, help_text="Broadcasted SSID if AP")
    connected_bssid = models.CharField(max_length=17, null=True, blank=True, db_index=True, help_text="For CLIENT type: MAC of the AP it is associated with")
    operating_channel = models.IntegerField(null=True, blank=True)
    is_encrypted = models.BooleanField(default=True)
    
    # Spatial Intelligence (Populated by the Python Middleware FSPL math)
    smoothed_rssi = models.IntegerField(null=True, blank=True, help_text="Averaged dBm to prevent multipath fading spikes")
    estimated_radius_meters = models.FloatField(null=True, blank=True, help_text="Calculated via Free-Space Path Loss")
    
    # Security & State Governance
    is_whitelisted = models.BooleanField(default=False, db_index=True, help_text="True if authorized by IT")
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = "infrastructure_assets"
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.mac_address} ({self.asset_type}) - Radius: {self.estimated_radius_meters}m"


class SecurityEvent(models.Model):
    """
    Only logs an entry when an Asset violates the established baseline or policy.
    """
    SEVERITY_LEVELS = [
        ('LOW', 'Low - Informational'),
        ('MEDIUM', 'Medium - Suspicious Behavior'),
        ('HIGH', 'High - Policy Violation'),
        ('CRITICAL', 'Critical - Active Threat'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='security_events')
    
    event_type = models.CharField(max_length=100, help_text="e.g., 'Shadow IT Detected', 'Radius Anomaly'")
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='MEDIUM', db_index=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "security_events"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.severity}] {self.event_type} - {self.asset.mac_address}"


class HunterDispatchLog(models.Model):
    """
    The Immutable Audit Ledger.
    Records every instance where the active Tactical Node is deployed.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Tracking in Progress'),
        ('RESOLVED', 'Threat Neutralized'),
        ('ORPHANED', 'Node Disconnected / Timeout'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    admin_id = models.CharField(max_length=150, help_text="Username of the Administrator who authorized the dispatch")
    target_asset = models.ForeignKey(Asset, on_delete=models.DO_NOTHING, related_name='dispatch_history')
    locked_channel = models.IntegerField(help_text="The exact channel the Hunter Node was commanded to lock onto")
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    resolution_notes = models.TextField(null=True, blank=True, help_text="Notes entered by Admin after physical resolution")

    class Meta:
        db_table = "audit_dispatch_ledger"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Dispatch {self.id} | Target: {self.target_asset.mac_address} | Status: {self.status}"


class SystemMessage(models.Model):
    """
    Operational logs, system health, and debug messages (from Kismet or the Middleware).
    Kept strictly separate from SecurityEvents.
    """
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug Trace'),
        ('INFO', 'General Information'),
        ('WARNING', 'Warning / Degradation'),
        ('ERROR', 'Component Error'),
        ('CRITICAL', 'Critical System Failure'),
    ]

    COMPONENT_CHOICES = [
        ('KISMET_API', 'Kismet Ingestion Engine'),
        ('MIDDLEWARE', 'Python Processing Pipeline'),
        ('DASHBOARD', 'Django Web UI'),
        ('HUNTER_NODE', 'Tactical Edge Node'),
        ('DATABASE', 'PostgreSQL / SSD'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO', db_index=True)
    component = models.CharField(max_length=20, choices=COMPONENT_CHOICES, default='MIDDLEWARE', db_index=True)
    message = models.TextField()

    class Meta:
        db_table = "system_messages"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.level}] {self.component}: {self.message[:50]}..."