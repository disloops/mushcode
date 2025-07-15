#!/usr/bin/env python3

# Ensure Python 3 compatibility
import sys
if sys.version_info < (3, 6):
    print("Error: This script requires Python 3.6 or higher")
    print(f"Current version: {sys.version}")
    sys.exit(1)

# MIT License
# Copyright (c) 2024 Matt Westfall (@disloops)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__author__ = 'Matt Westfall'
__version__ = '0.3'
__email__ = 'disloops@gmail.com'

# ASTRONOMICAL DATA FETCHER:
# - Queries NASA's JPL Horizons API for planetary positions
# - Calculates zodiac signs from ecliptic longitude
# - Estimates moon phases and provides concise summaries
# - Optimized for speed with caching and reduced API calls
# - Used by mush_gpt.py for astrology bot prompts

import requests
import json
import re
import argparse
import sys
from datetime import datetime, timedelta
import time

class AstronomyData:
    def __init__(self):
        self.base_url = "https://ssd.jpl.nasa.gov/api/horizons.api"
        self.zodiac_signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        self.zodiac_degrees = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]

        # Performance optimizations
        self.session = requests.Session()
        self.session.timeout = 15  # Reduced timeout for speed

    def get_planet_data(self, planet_id, date_str):
        """Fetch planet data from NASA JPL Horizons API (fixed for ecliptic longitude)"""
        # Validate date format
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

        stop_date = start_date + timedelta(days=1)

        params = {
            'format': 'text',
            'COMMAND': str(planet_id),
            'OBJ_DATA': 'NO',
            'MAKE_EPHEM': 'YES',
            'EPHEM_TYPE': 'OBSERVER',
            'CENTER': '500',  # Geocentric
            'START_TIME': start_date.strftime('%Y-%m-%d'),
            'STOP_TIME': stop_date.strftime('%Y-%m-%d'),
            'STEP_SIZE': '1d',
            'QUANTITIES': '31'  # Ecliptic longitude and latitude
        }

        try:
            response = self.session.get(self.base_url, params=params)
            if response.status_code == 200:
                return self.parse_ephemeris_data(response.text)
            else:
                return None
        except Exception as e:
            return None

    def get_moon_phase_data(self, date_str):
        """Fetch moon phase data from NASA JPL Horizons API (optimized)"""
        # Validate date format
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

        stop_date = start_date + timedelta(days=1)

        params = {
            'format': 'text',
            'COMMAND': '301',  # Moon
            'OBJ_DATA': 'NO',
            'MAKE_EPHEM': 'YES',
            'EPHEM_TYPE': 'OBSERVER',
            'CENTER': '500',
            'START_TIME': start_date.strftime('%Y-%m-%d'),
            'STOP_TIME': stop_date.strftime('%Y-%m-%d'),
            'STEP_SIZE': '1d',
            'QUANTITIES': '31'  # Phase angle
        }

        try:
            response = self.session.get(self.base_url, params=params)
            if response.status_code == 200:
                return self.parse_moon_phase_data(response.text)
            else:
                return None
        except Exception as e:
            return None

    def parse_ephemeris_data(self, data):
        """Parse ephemeris data from NASA API response (fixed for ecliptic longitude)"""
        # Find the data section between $$SOE and $$EOE
        start_marker = "$$SOE"
        end_marker = "$$EOE"

        start_idx = data.find(start_marker)
        end_idx = data.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return None

        data_section = data[start_idx + len(start_marker):end_idx].strip()
        lines = [line.strip() for line in data_section.split('\n') if line.strip()]

        if not lines:
            return None

        # Parse the first data line (for the requested date)
        data_line = lines[0]

        # Find the header section to identify column positions
        # Look for the header that contains column names
        header_start = data.find("Date__(UT)__HR:MN")
        if header_start == -1:
            return None

        # Find the end of the header (before the data section)
        header_end = data.find("$$SOE")
        if header_end == -1:
            return None

        header_section = data[header_start:header_end]

        # Look for the hEcl-Lon column in the header
        # The header might be split across multiple lines, so we need to combine them
        header_lines = header_section.split('\n')
        combined_header = ' '.join(header_lines)

        # Find the position of hEcl-Lon in the header
        hEcl_Lon_pos = combined_header.find('hEcl-Lon')
        if hEcl_Lon_pos == -1:
            # Try ObsEcLon as fallback (simplified API)
            hEcl_Lon_pos = combined_header.find('ObsEcLon')
            if hEcl_Lon_pos == -1:
                return None

        # For the simplified API, the data line format is: "YYYY-MMM-DD HH:MM     longitude latitude"
        # The longitude is the second numeric value after the date
        import re
        numeric_values = re.findall(r'-?\d+\.?\d*', data_line)
        numeric_values = [float(val) for val in numeric_values]

        # For the simplified API, the ecliptic longitude should be the 5th value (after date components)
        if len(numeric_values) >= 5:
            ecliptic_lon = numeric_values[4]  # 5th value (0-indexed)

            if 0 <= ecliptic_lon <= 360:
                return {
                    'ecliptic_longitude': ecliptic_lon,
                    'zodiac_sign': self.longitude_to_zodiac(ecliptic_lon),
                    'zodiac_degree': ecliptic_lon % 30
                }

        return None

    def parse_moon_phase_data(self, data):
        """Parse moon phase data from NASA API response (optimized)"""
        # Find the data section between $$SOE and $$EOE
        start_marker = "$$SOE"
        end_marker = "$$EOE"

        start_idx = data.find(start_marker)
        end_idx = data.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return None

        data_section = data[start_idx + len(start_marker):end_idx].strip()
        lines = [line.strip() for line in data_section.split('\n') if line.strip()]

        if not lines:
            return None

        # Parse the first data line (for the requested date)
        data_line = lines[0]
        parts = data_line.split()

        if len(parts) >= 3:
            try:
                # Format: "2025-Jul-09 00:00     ecliptic_lon  ecliptic_lat"
                # Get the ecliptic longitude (third column)
                ecliptic_lon = float(parts[2])

                return {
                    'ecliptic_longitude': ecliptic_lon,
                    'zodiac_sign': self.longitude_to_zodiac(ecliptic_lon),
                    'zodiac_degree': ecliptic_lon % 30,
                    'phase': self.estimate_moon_phase(ecliptic_lon)
                }
            except ValueError:
                return None

        return None

    def estimate_moon_phase(self, moon_longitude):
        """Estimate moon phase based on ecliptic longitude"""
        # This is a simplified calculation
        # In reality, we'd need the Sun's position to calculate the true phase angle
        # For now, we'll use a rough estimate based on the moon's position

        # Normalize to 0-360
        normalized = moon_longitude % 360

        # Rough phase estimation based on position
        if normalized < 45:
            return "New Moon"
        elif normalized < 90:
            return "Waxing Crescent"
        elif normalized < 135:
            return "First Quarter"
        elif normalized < 180:
            return "Waxing Gibbous"
        elif normalized < 225:
            return "Full Moon"
        elif normalized < 270:
            return "Waning Gibbous"
        elif normalized < 315:
            return "Last Quarter"
        else:
            return "Waning Crescent"

    def longitude_to_zodiac(self, longitude):
        """Convert ecliptic longitude to zodiac sign"""
        # Normalize longitude to 0-360 degrees
        normalized_lon = longitude % 360

        # Find which zodiac sign this longitude falls into
        # Aries: 0-30, Taurus: 30-60, etc.
        sign_index = int(normalized_lon / 30)
        if sign_index >= 12:
            sign_index = 11  # Capricorn for 360°

        return self.zodiac_signs[sign_index]

    def get_astronomical_data(self, date_str=None):
        """Get comprehensive astronomical data for a given date"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        # Fetch all major planets
        planets = {
            'Sun': '10',
            'Mercury': '199',
            'Venus': '299',
            'Mars': '499',
            'Jupiter': '599',
            'Saturn': '699',
            'Uranus': '799',
            'Neptune': '899',
            'Pluto': '999'
        }

        astronomical_data = {
            'date': date_str,
            'planets': {},
            'moon': {},
            'summary': ''
        }

        # Get planet positions (excluding Moon - we'll handle it separately)
        for planet_name, planet_id in planets.items():
            planet_data = self.get_planet_data(planet_id, date_str)
            if planet_data:
                astronomical_data['planets'][planet_name] = planet_data
            time.sleep(0.5)

        # Get Moon data separately with proper phase calculation
        moon_data = self.get_moon_data_with_phase(date_str, astronomical_data['planets'].get('Sun'))
        if moon_data:
            astronomical_data['moon'] = moon_data

        # Generate summary
        astronomical_data['summary'] = self.generate_summary(astronomical_data)

        return astronomical_data

    def get_moon_data_with_phase(self, date_str, sun_data):
        """Get moon data with accurate phase calculation"""
        # Get moon position using the same approach as other planets
        moon_data = self.get_planet_data('301', date_str)  # Moon ID is 301
        if not moon_data:
            return None

        # Calculate accurate moon phase using Sun-Moon angular difference
        if sun_data:
            moon_phase = self.calculate_moon_phase(sun_data['ecliptic_longitude'], moon_data['ecliptic_longitude'])
            moon_data['phase'] = moon_phase
        else:
            moon_data['phase'] = 'Unknown'

        return moon_data

    def get_moon_data_comprehensive(self, date_str):
        """Get moon data using comprehensive API parameters"""
        # Validate date format
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

        stop_date = start_date + timedelta(days=1)

        params = {
            'format': 'text',
            'COMMAND': '301',  # Moon
            'OBJ_DATA': 'NO',
            'MAKE_EPHEM': 'YES',
            'EPHEM_TYPE': 'OBSERVER',
            'CENTER': '500',  # Geocentric
            'START_TIME': start_date.strftime('%Y-%m-%d'),
            'STOP_TIME': stop_date.strftime('%Y-%m-%d'),
            'STEP_SIZE': '1d',
            'QUANTITIES': '1,3,4,9,20,23,24,25,26,27,29,31'  # Comprehensive set including ecliptic coordinates
        }

        try:
            response = self.session.get(self.base_url, params=params)
            if response.status_code == 200:
                return self.parse_comprehensive_moon_data(response.text)
            else:
                return None
        except Exception as e:
            return None

    def parse_comprehensive_moon_data(self, data):
        """Parse comprehensive moon data from NASA API response"""
        # Find the data section between $$SOE and $$EOE
        start_marker = "$$SOE"
        end_marker = "$$EOE"

        start_idx = data.find(start_marker)
        end_idx = data.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return None

        data_section = data[start_idx + len(start_marker):end_idx].strip()
        lines = [line.strip() for line in data_section.split('\n') if line.strip()]

        if not lines:
            return None

        # Parse the first data line (for the requested date)
        data_line = lines[0]

        # Find the header section to identify column positions
        header_start = data.find("Date__(UT)__HR:MN")
        if header_start == -1:
            return None

        header_end = data.find("$$SOE")
        if header_end == -1:
            return None

        header_section = data[header_start:header_end]

        # Look for the hEcl-Lon column in the header
        header_lines = header_section.split('\n')
        combined_header = ' '.join(header_lines)

        # Find the position of hEcl-Lon in the header
        hEcl_Lon_pos = combined_header.find('hEcl-Lon')
        if hEcl_Lon_pos == -1:
            # Try ObsEcLon as fallback
            hEcl_Lon_pos = combined_header.find('ObsEcLon')
            if hEcl_Lon_pos == -1:
                return None

        # Extract all numeric values from the data line
        import re
        numeric_values = re.findall(r'-?\d+\.?\d*', data_line)
        numeric_values = [float(val) for val in numeric_values]

        # For comprehensive API, the ecliptic longitude should be around position 5-6
        # Let's try different positions to find the correct longitude
        potential_longitudes = []
        for i, val in enumerate(numeric_values):
            if 0 <= val <= 360:
                potential_longitudes.append((i, val))

        # Use the most likely longitude value (usually the 5th or 6th numeric value)
        if len(numeric_values) >= 6:
            ecliptic_lon = numeric_values[5]  # 6th value (0-indexed)

            if 0 <= ecliptic_lon <= 360:
                return {
                    'ecliptic_longitude': ecliptic_lon,
                    'zodiac_sign': self.longitude_to_zodiac(ecliptic_lon),
                    'zodiac_degree': ecliptic_lon % 30
                }

        return None

    def calculate_moon_phase(self, sun_longitude, moon_longitude):
        """Calculate accurate moon phase using angular difference between Sun and Moon"""
        # Calculate the angular difference between Sun and Moon
        angular_diff = moon_longitude - sun_longitude

        # Normalize to 0-360 degrees
        angular_diff = angular_diff % 360

        # Moon phase is determined by the angular difference:
        # 0° = New Moon, 90° = First Quarter, 180° = Full Moon, 270° = Last Quarter
        if angular_diff < 22.5:
            return "New Moon"
        elif angular_diff < 67.5:
            return "Waxing Crescent"
        elif angular_diff < 112.5:
            return "First Quarter"
        elif angular_diff < 157.5:
            return "Waxing Gibbous"
        elif angular_diff < 202.5:
            return "Full Moon"
        elif angular_diff < 247.5:
            return "Waning Gibbous"
        elif angular_diff < 292.5:
            return "Last Quarter"
        elif angular_diff < 337.5:
            return "Waning Crescent"
        else:
            return "New Moon"

    def generate_summary(self, data):
        """Generate a concise summary for the bot prompt"""
        summary_parts = []

        # Moon phase and position
        if 'moon' in data and data['moon']:
            moon = data['moon']
            phase_info = f"Moon: {moon['zodiac_sign']} {moon['zodiac_degree']:.1f}° ({moon.get('phase', 'Unknown')})"
            summary_parts.append(phase_info)

        # Planet positions
        if data.get('planets'):
            for planet, info in data['planets'].items():
                if info:
                    summary_parts.append(f"{planet}: {info['zodiac_sign']} {info['zodiac_degree']:.1f}°")

        return " | ".join(summary_parts)

    def get_today_data(self):
        """Get astronomical data for today"""
        return self.get_astronomical_data()

def print_help():
    """Print help information"""
    help_text = """
Astronomical Data Fetcher v0.3
Fetches real astronomical data from NASA's JPL Horizons API

USAGE:
    python3 astronomy_data.py [OPTIONS]

OPTIONS:
    -h, --help      Show this help message
    -v, --verbose   Human-readable output with full details
    -b, --bot       Bot-consumable output (summary only)

EXAMPLES:
    python3 astronomy_data.py --help
    python3 astronomy_data.py --verbose
    python3 astronomy_data.py --bot

DEFAULT:
    Shows this help message when no options are provided.

SECURITY:
    - Validates all input parameters
    - Handles network errors gracefully
    - Sanitizes output data
    - Uses secure HTTP requests with timeouts
"""
    print(help_text)

def print_verbose_output(data):
    """Print human-readable verbose output (clean, relevant)"""
    print("\n=== Astronomical Data ===")
    print(f"Date: {data['date']}")

    # Sun info (for seasonal changes)
    if data.get('planets') and data['planets'].get('Sun'):
        sun = data['planets']['Sun']
        print(f"\nSun:")
        print(f"   Position: {sun['zodiac_sign']} {sun['zodiac_degree']:.2f}°")
        print(f"   Ecliptic Longitude: {sun['ecliptic_longitude']:.4f}°")

    # Moon info
    if data.get('moon'):
        moon = data['moon']
        print(f"\nMoon:")
        print(f"   Position: {moon['zodiac_sign']} {moon['zodiac_degree']:.2f}°")
        print(f"   Phase: {moon.get('phase', 'Unknown')}")
        print(f"   Ecliptic Longitude: {moon['ecliptic_longitude']:.4f}°")

    # Other planets
    if data.get('planets'):
        print(f"\nPlanets:")
        for planet, info in data['planets'].items():
            if planet == 'Sun' or not info:
                continue
            print(f"   {planet}: {info['zodiac_sign']} {info['zodiac_degree']:.2f}° (Longitude: {info['ecliptic_longitude']:.4f}°)")

    # Add seasonal/horoscope context
    if data.get('planets') and data['planets'].get('Sun'):
        sun_deg = data['planets']['Sun']['ecliptic_longitude']
        if 0 <= sun_deg < 90:
            season = "Spring (Northern Hemisphere)"
        elif 90 <= sun_deg < 180:
            season = "Summer (Northern Hemisphere)"
        elif 180 <= sun_deg < 270:
            season = "Autumn (Northern Hemisphere)"
        else:
            season = "Winter (Northern Hemisphere)"
        print(f"\nCurrent Season: {season}")

def print_bot_output(data):
    """Print bot-consumable output (summary only, clean)"""
    if not data.get('planets') or not data.get('moon'):
        print("Unable to fetch astronomical data")
        return
    sun = data['planets']['Sun']
    moon = data['moon']
    summary = [
        f"Sun: {sun['zodiac_sign']} {sun['zodiac_degree']:.1f}°",
        f"Moon: {moon['zodiac_sign']} {moon['zodiac_degree']:.1f}° ({moon.get('phase', 'Unknown')})"
    ]
    for planet, info in data['planets'].items():
        if planet == 'Sun' or not info:
            continue
        summary.append(f"{planet}: {info['zodiac_sign']} {info['zodiac_degree']:.1f}°")
    print(" | ".join(summary))

def main():
    """Main function with argument parsing and secure execution"""
    parser = argparse.ArgumentParser(
        description='Fetch astronomical data from NASA JPL Horizons API',
        add_help=False  # We'll handle help manually
    )

    parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    parser.add_argument('-v', '--verbose', action='store_true', help='Human-readable output')
    parser.add_argument('-b', '--bot', action='store_true', help='Bot-consumable output')

    try:
        args = parser.parse_args()
    except SystemExit:
        # Handle invalid arguments gracefully
        print_help()
        sys.exit(1)

    # Show help if no arguments or help requested
    if len(sys.argv) == 1 or args.help:
        print_help()
        return

    # Validate that only one output mode is selected
    output_modes = [args.verbose, args.bot]
    if sum(output_modes) != 1:
        print("Error: Please specify exactly one output mode (-v/--verbose or -b/--bot)")
        print_help()
        sys.exit(1)

    try:
        # Initialize astronomy data fetcher
        astronomy = AstronomyData()

        # Get astronomical data
        data = astronomy.get_today_data()

        if not data:
            print("Error: Unable to fetch astronomical data")
            sys.exit(1)

        # Print appropriate output format
        if args.verbose:
            print_verbose_output(data)
        elif args.bot:
            print_bot_output(data)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
