"""
Device discovery module for Who's Home application
Implements various methods to discover and monitor devices on the LAN
"""

import subprocess
import platform
import socket
import threading
import time
import logging
import ipaddress
import re
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class DeviceDiscovery:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.settings = {}
        self.update_settings_from_db()
    
    def update_settings_from_db(self):
        """Update settings from database"""
        if self.db_manager:
            self.settings = self.db_manager.get_settings()
    
    def update_settings(self, new_settings):
        """Update discovery settings"""
        self.settings.update(new_settings)
    
    def get_network_range(self) -> str:
        """Get network range from settings or auto-detect"""
        network_range = self.settings.get('network_range', 'auto')
        
        if network_range == 'auto':
            # Auto-detect network range using multiple methods
            try:
                gateway = None
                
                # Try different commands to find default gateway
                route_commands = [
                    ['ip', 'route', 'show', 'default'],     # Linux/Unix
                    ['route', 'print'],                     # Windows
                    ['netstat', '-rn'],                     # Generic Unix
                ]
                
                for cmd in route_commands:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                # Look for default route patterns
                                if 'default via' in line:  # Linux ip route
                                    parts = line.split()
                                    if len(parts) >= 3:
                                        gateway = parts[2]
                                        break
                                elif '0.0.0.0' in line and 'Gateway' not in line:  # Windows route
                                    parts = line.split()
                                    if len(parts) >= 3:
                                        gateway = parts[2]
                                        break
                                elif '0.0.0.0' in line:  # Generic netstat
                                    parts = line.split()
                                    for part in parts:
                                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', part) and part != '0.0.0.0':
                                            gateway = part
                                            break
                            if gateway:
                                break
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                
                # Convert gateway to network range
                if gateway:
                    network_parts = gateway.split('.')
                    if len(network_parts) == 4:
                        network_range = f"{'.'.join(network_parts[:3])}.0/24"
                        logger.info(f"Auto-detected network range: {network_range}")
                    else:
                        raise ValueError("Invalid gateway format")
                else:
                    raise ValueError("No gateway found")
                                        
            except Exception as e:
                logger.warning(f"Could not auto-detect network range: {e}")
                # Try common ranges as fallback
                common_ranges = ['192.168.1.0/24', '192.168.0.0/24', '10.0.0.0/24']
                network_range = common_ranges[0]
                logger.info(f"Using fallback network range: {network_range}")
        
        return network_range
    
    def ping_device(self, ip_address: str) -> bool:
        """Ping a device to check if it's online"""
        try:
            timeout = self.settings.get('ping_timeout', 1)
            
            # Try standard Linux/Unix ping first
            cmd = ['ping', '-c', '1', '-W', str(timeout), ip_address]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
            
            if result.returncode == 0:
                return True
            
            # Fallback: try Windows-style ping if Linux failed
            cmd = ['ping', '-n', '1', '-w', str(int(timeout * 1000)), ip_address]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            logger.debug(f"Ping error for {ip_address}: {e}")
            return False
    
    def arping_device(self, ip_address: str) -> Tuple[bool, Optional[str]]:
        """Use arping to check device and get MAC address"""
        try:
            timeout = self.settings.get('arping_timeout', 2)
            
            # Try arping first (Linux/Unix)
            try:
                result = subprocess.run(['arping', '-c', '1', '-w', str(timeout), ip_address], 
                                      capture_output=True, text=True, timeout=timeout + 1)
                if result.returncode == 0:
                    # Parse arping output for MAC
                    for line in result.stdout.split('\n'):
                        mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', 
                                            line.lower())
                        if mac_match:
                            return True, mac_match.group(1).upper()
                    return True, None  # Device responded but no MAC found
            except FileNotFoundError:
                pass  # arping not available, continue to fallback
            
            # Fallback: Use arp command
            for arp_cmd in [['arp', '-a', ip_address], ['arp', '-n', ip_address]]:
                try:
                    result = subprocess.run(arp_cmd, capture_output=True, text=True, timeout=timeout)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if ip_address in line:
                                # Look for MAC address pattern (Windows format)
                                mac_match = re.search(r'([0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2})', 
                                                    line.lower())
                                if mac_match:
                                    mac = mac_match.group(1).replace('-', ':')
                                    return True, mac.upper()
                                
                                # Look for MAC address pattern (Linux format)
                                mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', 
                                                    line.lower())
                                if mac_match:
                                    return True, mac_match.group(1).upper()
                except FileNotFoundError:
                    continue
            
            return False, None
                
        except subprocess.TimeoutExpired:
            return False, None
        except Exception as e:
            logger.debug(f"Arping error for {ip_address}: {e}")
            return False, None
    
    def get_mac_from_arp_table(self, ip_address: str) -> Tuple[bool, Optional[str]]:
        """Get MAC address from system ARP table"""
        try:
            # Try multiple ARP command variations
            arp_commands = [
                ['arp', '-n'],          # Linux standard
                ['arp', '-a'],          # Windows standard  
                ['ip', 'neighbor'],     # Modern Linux
            ]
            
            for cmd in arp_commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if ip_address in line:
                                # Look for Windows format MAC (aa-bb-cc-dd-ee-ff)
                                mac_match = re.search(r'([0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2})', 
                                                    line.lower())
                                if mac_match:
                                    mac = mac_match.group(1).replace('-', ':').upper()
                                    return True, mac
                                
                                # Look for Linux format MAC (aa:bb:cc:dd:ee:ff)
                                mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', 
                                                    line.lower())
                                if mac_match:
                                    return True, mac_match.group(1).upper()
                                
                                # Look for 'ip neighbor' format with lladdr
                                if 'lladdr' in line:
                                    parts = line.split()
                                    for i, part in enumerate(parts):
                                        if part == 'lladdr' and i + 1 < len(parts):
                                            mac_candidate = parts[i + 1]
                                            if re.match(r'^[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}$', 
                                                       mac_candidate.lower()):
                                                return True, mac_candidate.upper()
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            
            return False, None
            
        except Exception as e:
            logger.debug(f"ARP table lookup error for {ip_address}: {e}")
            return False, None
    
    def populate_arp_table(self, network_range: str):
        """Populate ARP table by pinging all IPs quickly"""
        try:
            network = ipaddress.ip_network(network_range, strict=False)
            logger.info("Pre-populating ARP table...")
            
            # Quick ping sweep to populate ARP table
            processes = []
            for ip in network.hosts():
                if len(processes) >= 50:  # Limit concurrent processes
                    for p in processes:
                        p.wait()
                    processes = []
                
                # Try Linux/Unix ping first, then Windows as fallback
                for cmd in [
                    ['ping', '-c', '1', '-W', '1', str(ip)],
                    ['ping', '-n', '1', '-w', '100', str(ip)]
                ]:
                    try:
                        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        processes.append(proc)
                        break  # Use first working command
                    except FileNotFoundError:
                        continue
            
            # Wait for remaining processes
            for proc in processes:
                proc.wait()
            
            logger.info("ARP table population completed")
        except Exception as e:
            logger.debug(f"Error populating ARP table: {e}")

    def scan_network_range(self) -> List[Dict]:
        """Scan entire network range for devices"""
        discovered_devices = []
        network_range = self.get_network_range()
        
        try:
            network = ipaddress.ip_network(network_range, strict=False)
            discovery_methods = self.settings.get('discovery_methods', ['ping', 'arping'])
            
            logger.info(f"Scanning network range: {network_range}")
            
            # Pre-populate ARP table for better MAC detection
            self.populate_arp_table(network_range)
            
            # Use threading to speed up discovery
            def scan_ip(ip_str):
                device_info = {
                    'ip_address': ip_str,
                    'mac_address': None,
                    'hostname': None,
                    'is_online': False,
                    'discovery_method': None
                }
                
                # Try different discovery methods
                for method in discovery_methods:
                    if method == 'ping':
                        if self.ping_device(ip_str):
                            device_info['is_online'] = True
                            device_info['discovery_method'] = 'ping'
                            # Try to get MAC from ARP table after ping
                            _, mac = self.get_mac_from_arp_table(ip_str)
                            if mac:
                                device_info['mac_address'] = mac
                            break
                    
                    elif method == 'arping':
                        is_online, mac = self.arping_device(ip_str)
                        if is_online:
                            device_info['is_online'] = True
                            device_info['discovery_method'] = 'arping'
                            if mac:
                                device_info['mac_address'] = mac
                            break
                
                # If device is online but no MAC found, try additional methods
                if device_info['is_online'] and not device_info['mac_address']:
                    # Try arping specifically to get MAC if we only got ping response
                    if device_info['discovery_method'] == 'ping':
                        _, mac = self.arping_device(ip_str)
                        if mac:
                            device_info['mac_address'] = mac
                    
                    # Final attempt: check ARP table again after a small delay
                    if not device_info['mac_address']:
                        time.sleep(0.1)  # Small delay for ARP table to update
                        _, mac = self.get_mac_from_arp_table(ip_str)
                        if mac:
                            device_info['mac_address'] = mac
                
                # Try to resolve hostname
                if device_info['is_online']:
                    try:
                        hostname = socket.gethostbyaddr(ip_str)[0]
                        device_info['hostname'] = hostname
                    except socket.herror:
                        pass
                    
                    # Log discovery attempt
                    if self.db_manager:
                        self.db_manager.log_discovery(
                            device_info['mac_address'],
                            ip_str,
                            device_info['discovery_method'],
                            device_info['is_online']
                        )
                
                if device_info['is_online']:
                    discovered_devices.append(device_info)
            
            # Create threads for parallel scanning
            threads = []
            for ip in network.hosts():
                if len(threads) >= 50:  # Limit concurrent threads
                    for t in threads:
                        t.join()
                    threads = []
                
                thread = threading.Thread(target=scan_ip, args=(str(ip),))
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            # Wait for remaining threads
            for thread in threads:
                thread.join()
            
            logger.info(f"Network scan completed. Found {len(discovered_devices)} devices")
            return discovered_devices
            
        except Exception as e:
            logger.error(f"Error scanning network range: {e}")
            return []
    
    def discover_all_devices(self) -> List[Dict]:
        """Discover all devices on the network"""
        return self.scan_network_range()
    
    def check_device_status(self, mac_address: str) -> bool:
        """Check if a specific device (by MAC) is online"""
        try:
            # First, try to find IP in ARP table
            ip_address = self.get_ip_from_mac(mac_address)
            
            if ip_address:
                # Test the known IP
                discovery_methods = self.settings.get('discovery_methods', ['ping', 'arping'])
                
                for method in discovery_methods:
                    if method == 'ping' and self.ping_device(ip_address):
                        return True
                    elif method == 'arping':
                        is_online, _ = self.arping_device(ip_address)
                        if is_online:
                            return True
            
            # If not found in ARP or not responding, do a limited network scan
            # Only scan common IP ranges to avoid full network scan on every check
            current_range = self.get_network_range()
            common_ranges = [current_range, '192.168.1.0/24', '192.168.0.0/24', '10.0.0.0/24']
            
            for range_str in common_ranges:
                try:
                    network = ipaddress.ip_network(range_str, strict=False)
                    # Only scan first 50 IPs to keep it fast
                    for i, ip in enumerate(network.hosts()):
                        if i >= 50:
                            break
                        
                        is_online, found_mac = self.arping_device(str(ip))
                        if is_online and found_mac and found_mac.upper() == mac_address.upper():
                            return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking device status for {mac_address}: {e}")
            return False
    
    def get_ip_from_mac(self, mac_address: str) -> Optional[str]:
        """Get IP address from MAC address using ARP table"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
            else:
                result = subprocess.run(['arp', '-n'], capture_output=True, text=True)
            
            if result.returncode == 0:
                mac_normalized = mac_address.upper()
                
                for line in result.stdout.split('\n'):
                    if platform.system() == "Windows":
                        # Windows format: 192.168.1.100    aa-bb-cc-dd-ee-ff     dynamic
                        mac_match = re.search(r'([0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2}-[0-9a-f]{2})', 
                                            line.lower())
                        if mac_match:
                            found_mac = mac_match.group(1).replace('-', ':').upper()
                            if found_mac == mac_normalized:
                                # Extract IP from the line
                                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                                if ip_match:
                                    return ip_match.group(1)
                    else:
                        # Linux format: 192.168.1.100 ether aa:bb:cc:dd:ee:ff C eth0
                        mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', 
                                            line.lower())
                        if mac_match:
                            found_mac = mac_match.group(1).upper()
                            if found_mac == mac_normalized:
                                # Extract IP from the line  
                                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                                if ip_match:
                                    return ip_match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting IP from MAC {mac_address}: {e}")
            return None
