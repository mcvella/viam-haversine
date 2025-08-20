from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple, cast, Union)
import re
from datetime import datetime, timedelta

from typing_extensions import Self
from viam.components.sensor import *
from viam.components.movement_sensor import MovementSensor
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import SensorReading, ValueTypes, struct_to_dict
from haversine import haversine, Unit


class Haversine(Sensor, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam-soleng", "haversine"), "haversine")

    def __init__(self, name: str):
        super().__init__(name)
        self.sensor_1 = None
        self.sensor_2 = None
        self.sensor1_lat_path = None
        self.sensor1_lng_path = None
        self.sensor1_updated_path = None
        self.sensor1_expire = None
        self.sensor2_lat_path = None
        self.sensor2_lng_path = None
        self.sensor2_updated_path = None
        self.sensor2_expire = None

    def _get_component_type(self, component: ResourceBase) -> str:
        """Determine if a component is a Sensor or MovementSensor.
        
        Args:
            component: The component to check
            
        Returns:
            str: Either 'sensor' or 'movement_sensor'
        """
        if isinstance(component, MovementSensor):
            return 'movement_sensor'
        elif isinstance(component, Sensor):
            return 'sensor'
        else:
            raise Exception(f"Component must be either Sensor or MovementSensor, got {type(component)}")

    def _parse_duration(self, duration_str: str) -> timedelta:
        """Parse duration string like '1d', '12h', '10m', '30s', '100ms' into timedelta.
        
        Args:
            duration_str: Duration string in format like '1d', '12h', '10m', '30s', '100ms'
            
        Returns:
            timedelta: The parsed duration
            
        Raises:
            ValueError: If duration format is invalid
        """
        pattern = r'^(\d+)(d|h|m|s|ms)$'
        match = re.match(pattern, duration_str)
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}. Expected format like '1d', '12h', '10m', '30s', '100ms'")
        
        value = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'd':
            return timedelta(days=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 's':
            return timedelta(seconds=value)
        elif unit == 'ms':
            return timedelta(milliseconds=value)
        else:
            raise ValueError(f"Unknown duration unit: {unit}")

    def _is_reading_valid(self, reading: Dict, updated_path: Optional[List[str]], expire_duration: Optional[timedelta]) -> bool:
        """Check if a sensor reading is still valid based on updated timestamp and expire duration.
        
        Args:
            reading: The sensor reading dictionary
            updated_path: Path to the updated timestamp field
            expire_duration: Duration after which the reading expires
            
        Returns:
            bool: True if reading is valid, False otherwise
        """
        if updated_path is None or expire_duration is None:
            return True
            
        try:
            updated_str = self._get_nested_value(reading, updated_path, return_str=True)
            updated_time = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
            now = datetime.now(updated_time.tzinfo) if updated_time.tzinfo else datetime.now()
            
            return (now - updated_time) <= expire_duration
        except Exception as e:
            self.logger.warn(f"Error checking reading validity: {str(e)}")
            return False

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        attributes = struct_to_dict(config.attributes)
        optional_deps = []

        if "sensor_1" in attributes:
            sensor1 = attributes["sensor_1"]
            if not all(key in sensor1 for key in ["name", "latitude", "longitude"]):
                raise Exception("sensor_1 if configured must have name, latitude, and longitude fields")
            optional_deps.append(str(sensor1["name"]))

        if "sensor_2" in attributes:
            sensor2 = attributes["sensor_2"]
            if not all(key in sensor2 for key in ["name", "latitude", "longitude"]):
                raise Exception("sensor_2 if configured must have name, latitude, and longitude fields")
            optional_deps.append(str(sensor2["name"]))

        return [], optional_deps

    def _find_component(self, name: str, dependencies: Mapping[ResourceName, ResourceBase]) -> Optional[Tuple[ResourceBase, str]]:
        """Find a component by name, trying both Sensor and MovementSensor resource types.
        
        Args:
            name: The component name
            dependencies: Available dependencies
            
        Returns:
            Tuple of (component, component_type) if found, None otherwise
        """
        # Try Sensor first
        sensor_name = Sensor.get_resource_name(name)
        if sensor_name in dependencies:
            component = dependencies[sensor_name]
            component_type = self._get_component_type(component)
            return component, component_type
            
        # Try MovementSensor
        movement_sensor_name = MovementSensor.get_resource_name(name)
        if movement_sensor_name in dependencies:
            component = dependencies[movement_sensor_name]
            component_type = self._get_component_type(component)
            return component, component_type
            
        return None

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        attributes = struct_to_dict(config.attributes)

        # Reset all sensor configurations
        self.sensor_1 = None
        self.sensor_2 = None
        self.sensor1_lat_path = None
        self.sensor1_lng_path = None
        self.sensor1_updated_path = None
        self.sensor1_expire = None
        self.sensor2_lat_path = None
        self.sensor2_lng_path = None
        self.sensor2_updated_path = None
        self.sensor2_expire = None

        if "sensor_1" in attributes:
            sensor1 = attributes["sensor_1"]
            result = self._find_component(str(sensor1["name"]), dependencies)
            if result:
                component, component_type = result
                self.logger.info(f"Configuring sensor_1 as {component_type}")
                
                if component_type == 'movement_sensor':
                    self.sensor_1 = cast(MovementSensor, component)
                else:
                    self.sensor_1 = cast(Sensor, component)
                    
                self.sensor1_lat_path = str(sensor1["latitude"]).split(".")
                self.sensor1_lng_path = str(sensor1["longitude"]).split(".")
                
                if "updated" in sensor1:
                    self.sensor1_updated_path = str(sensor1["updated"]).split(".")
                if "expire" in sensor1:
                    self.sensor1_expire = self._parse_duration(str(sensor1["expire"]))
            else:
                self.logger.warn(f"Configured sensor_1 '{sensor1['name']}' not found in dependencies (tried both Sensor and MovementSensor)")

        if "sensor_2" in attributes:
            sensor2 = attributes["sensor_2"]
            result = self._find_component(str(sensor2["name"]), dependencies)
            if result:
                component, component_type = result
                self.logger.info(f"Configuring sensor_2 as {component_type}")
                
                if component_type == 'movement_sensor':
                    self.sensor_2 = cast(MovementSensor, component)
                else:
                    self.sensor_2 = cast(Sensor, component)
                    
                self.sensor2_lat_path = str(sensor2["latitude"]).split(".")
                self.sensor2_lng_path = str(sensor2["longitude"]).split(".")
                
                if "updated" in sensor2:
                    self.sensor2_updated_path = str(sensor2["updated"]).split(".")
                if "expire" in sensor2:
                    self.sensor2_expire = self._parse_duration(str(sensor2["expire"]))
            else:
                self.logger.warn(f"Configured sensor_2 '{sensor2['name']}' not found in dependencies (tried both Sensor and MovementSensor)")

        if not all([self.sensor_1, self.sensor_2]):
            self.logger.warn("One or both sensors not configured - get_readings() will return empty results. Only do_command() will be fully functional.")

    def _get_nested_value(self, data: Dict, path: List[str], return_str: bool = False) -> Any:
        """Helper function to get nested dictionary values using a path.
        
        Args:
            data: Dictionary containing sensor readings
            path: List of keys to traverse to find the value
            return_str: If True, return the raw value as string instead of converting to float
            
        Returns:
            float or str: The extracted value
            
        Raises:
            Exception: If the path is invalid or value cannot be converted to float
        """
        self.logger.debug(f"Getting nested value for path {'.'.join(path)} from data: {data}")
        
        current = data
        for i, key in enumerate(path):
            self.logger.debug(f"Step {i}: accessing key '{key}' from current: {current} (type: {type(current)})")
            
            if not isinstance(current, dict):
                # Handle special Viam objects like GeoPoint
                if hasattr(current, key):
                    current = getattr(current, key)
                else:
                    raise Exception(f"Cannot access '{key}' in path {'.'.join(path)}, parent is not a dictionary and has no attribute '{key}': {current}")
            else:
                if key not in current:
                    raise Exception(f"Key '{key}' not found in path {'.'.join(path)}")
                current = current[key]
            
        # Handle case where value might be in a 'value' field
        if isinstance(current, dict) and "value" in current:
            current = current["value"]
            
        self.logger.debug(f"Final value: {current} (type: {type(current)})")
            
        if return_str:
            return str(current)
            
        try:
            return float(current)
        except (ValueError, TypeError):
            raise Exception(f"Could not convert value to float at path {'.'.join(path)}: {current}")

    def _calculate_distances(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> Dict[str, Any]:
        """Calculate distances between two points in different units.
        
        Args:
            point1: Tuple of (latitude, longitude) for first point
            point2: Tuple of (latitude, longitude) for second point
            
        Returns:
            Dict containing distances in km, miles, nautical miles and the input locations
        """
        distance_km = haversine(point1, point2, unit=Unit.KILOMETERS)
        distance_mi = haversine(point1, point2, unit=Unit.MILES)
        distance_nm = haversine(point1, point2, unit=Unit.NAUTICAL_MILES)
        
        return {
            "distance_km": distance_km,
            "distance_miles": distance_mi,
            "distance_nautical_miles": distance_nm,
            "location_1": {"latitude": point1[0], "longitude": point1[1]},
            "location_2": {"latitude": point2[0], "longitude": point2[1]}
        }

    async def get_readings(
        self,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, SensorReading]:
        if not all([self.sensor_1, self.sensor_2]):
            return {}

        readings1 = await self.sensor_1.get_readings(timeout=timeout)
        readings2 = await self.sensor_2.get_readings(timeout=timeout)

        self.logger.debug(f"Sensor 1 readings: {readings1}")
        self.logger.debug(f"Sensor 2 readings: {readings2}")
        self.logger.debug(f"Sensor 1 paths - lat: {'.'.join(self.sensor1_lat_path)}, lng: {'.'.join(self.sensor1_lng_path)}")
        self.logger.debug(f"Sensor 2 paths - lat: {'.'.join(self.sensor2_lat_path)}, lng: {'.'.join(self.sensor2_lng_path)}")

        try:
            # Check if readings are still valid
            if not self._is_reading_valid(readings1, self.sensor1_updated_path, self.sensor1_expire):
                self.logger.warn("Sensor 1 reading has expired")
                return {}
                
            if not self._is_reading_valid(readings2, self.sensor2_updated_path, self.sensor2_expire):
                self.logger.warn("Sensor 2 reading has expired")
                return {}

            # Extract coordinates using the configured paths
            lat1 = self._get_nested_value(readings1, self.sensor1_lat_path)
            lng1 = self._get_nested_value(readings1, self.sensor1_lng_path)
            lat2 = self._get_nested_value(readings2, self.sensor2_lat_path)
            lng2 = self._get_nested_value(readings2, self.sensor2_lng_path)

            self.logger.debug(f"Extracted coordinates - Point 1: ({lat1}, {lng1}), Point 2: ({lat2}, {lng2})")
            return self._calculate_distances((lat1, lng1), (lat2, lng2))
        except Exception as e:
            self.logger.error(f"Error extracting coordinates: {str(e)}")
            raise

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        if "location_1" in command and "location_2" in command:
            loc1 = cast(Dict[str, float], command["location_1"])
            loc2 = cast(Dict[str, float], command["location_2"])

            point1 = (loc1["latitude"], loc1["longitude"])
            point2 = (loc2["latitude"], loc2["longitude"])
            
            return self._calculate_distances(point1, point2)
        
        raise Exception("Both location_1 and location_2 must be provided in the format: {'latitude': float, 'longitude': float}")

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> List[Geometry]:
        return []

