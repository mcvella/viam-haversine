from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple, cast)

from typing_extensions import Self
from viam.components.sensor import *
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import SensorReading, ValueTypes, struct_to_dict
from haversine import haversine, Unit


class Haversine(Sensor, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily("mcvella", "haversine"), "haversine")

    def __init__(self, name: str):
        super().__init__(name)
        self.sensor_1 = None
        self.sensor_2 = None
        self.sensor1_lat_path = None
        self.sensor1_lng_path = None
        self.sensor2_lat_path = None
        self.sensor2_lng_path = None

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

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        attributes = struct_to_dict(config.attributes)

        # Reset all sensor configurations
        self.sensor_1 = None
        self.sensor_2 = None
        self.sensor1_lat_path = None
        self.sensor1_lng_path = None
        self.sensor2_lat_path = None
        self.sensor2_lng_path = None

        if "sensor_1" in attributes:
            sensor1 = attributes["sensor_1"]
            sensor_name = Sensor.get_resource_name(str(sensor1["name"]))
            if sensor_name in dependencies:
                self.sensor_1 = cast(Sensor, dependencies[sensor_name])
                self.sensor1_lat_path = str(sensor1["latitude"]).split(".")
                self.sensor1_lng_path = str(sensor1["longitude"]).split(".")
            else:
                self.logger.warn(f"Configured sensor_1 '{sensor1['name']}' not found in dependencies")

        if "sensor_2" in attributes:
            sensor2 = attributes["sensor_2"]
            sensor_name = Sensor.get_resource_name(str(sensor2["name"]))
            if sensor_name in dependencies:
                self.sensor_2 = cast(Sensor, dependencies[sensor_name])
                self.sensor2_lat_path = str(sensor2["latitude"]).split(".")
                self.sensor2_lng_path = str(sensor2["longitude"]).split(".")
            else:
                self.logger.warn(f"Configured sensor_2 '{sensor2['name']}' not found in dependencies")

        if not all([self.sensor_1, self.sensor_2]):
            self.logger.warn("One or both sensors not configured - get_readings() will return empty results. Only do_command() will be fully functional.")

    def _get_nested_value(self, data: Dict, path: List[str]) -> float:
        """Helper function to get nested dictionary values using a path.
        
        Args:
            data: Dictionary containing sensor readings
            path: List of keys to traverse to find the value
            
        Returns:
            float: The extracted coordinate value
            
        Raises:
            Exception: If the path is invalid or value cannot be converted to float
        """
        current = data
        for key in path:
            if not isinstance(current, dict):
                raise Exception(f"Cannot access '{key}' in path {'.'.join(path)}, parent is not a dictionary: {current}")
            if key not in current:
                raise Exception(f"Key '{key}' not found in path {'.'.join(path)}")
            current = current[key]
            
        # Handle case where value might be in a 'value' field
        if isinstance(current, dict) and "value" in current:
            current = current["value"]
            
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

