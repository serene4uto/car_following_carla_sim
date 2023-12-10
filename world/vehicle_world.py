import carla
import sys
import random

from .utils import get_actor_blueprints, get_actor_display_name
from .camera import DrivingViewCamera, DepthCamera

class VehicleWorld(object):
    def __init__(self, 
                 carla_world, 
                 hud, 
                 sync = False,
                 rolename = 'hero',
                 spawn_point_idx = 0,
                 filter='vehicle.*',
                 ):
        
        self.world = carla_world
        self.sync = sync
        self.actor_role_name = rolename
        self.spawn_point_idx = spawn_point_idx
        self._autopilot_enabled = False


        try:
            self.map = self.world.get_map()
        except RuntimeError as error:
            print('RuntimeError: {}'.format(error))
            print('  The server could not send the OpenDRIVE (.xodr) file:')
            print('  Make sure it exists, has the same name of your town, and is correct.')
            sys.exit(1)

        self.hud = hud
        self.player = None

        # Define Sensors
        # self.collision_sensor = None
        # self.lane_invasion_sensor = None
        # self.gnss_sensor = None
        # self.imu_sensor = None
        # self.radar_sensor = None

        # Define Driving View Camera
        self.driving_view_camera = None

        self._actor_filter = filter

        self.restart()

        self.world.on_tick(self.hud.on_world_tick) # Register the tick function of the hud to the world tick event.



    def restart(self) -> None:      
        # Keep same driving view camera config if already exists.
        driving_view_index = self.driving_view_camera.index if self.driving_view_camera is not None else 0
        cam_pos_index = self.driving_view_camera.transform_index if self.driving_view_camera is not None else 0

        # Get a vehicle blueprint and set parameters.
        # Get a random blueprint.
        blueprint = random.choice(self.world.get_blueprint_library().filter(self._actor_filter))

        blueprint.set_attribute('role_name', self.actor_role_name) # Set the role name of the vehicle.
        if blueprint.has_attribute('terramechanics'):
            blueprint.set_attribute('terramechanics', 'true')
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)
        if blueprint.has_attribute('driver_id'):
            driver_id = random.choice(blueprint.get_attribute('driver_id').recommended_values)
            blueprint.set_attribute('driver_id', driver_id)
        if blueprint.has_attribute('is_invincible'):
            blueprint.set_attribute('is_invincible', 'true')

        # Spawn the player.
        if self.player is not None:
            spawn_point = self.player.get_transform()
            spawn_point.location.z += 2.0
            spawn_point.rotation.roll = 0.0
            spawn_point.rotation.pitch = 0.0
            self.destroy()
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
            self.modify_vehicle_physics(self.player)
        while self.player is None:
            if not self.map.get_spawn_points():
                print('There are no spawn points available in your map/town.')
                print('Please add some Vehicle Spawn Point to your UE4 scene.')
                sys.exit(1)
            spawn_points = self.map.get_spawn_points()

            if self.spawn_point_idx != None:
                # Spawn the player at the specific spawn point. TODO: Make this configurable.
                spawn_point = spawn_points[self.spawn_point_idx] if spawn_points else carla.Transform()
            else:
                spawn_point = random.choice(spawn_points) if spawn_points else carla.Transform() #TODO: ??

            # print(spawn_points.index(spawn_point))


            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
            self.modify_vehicle_physics(self.player)

        
        # Set up Driving View Camera
        self.driving_view_camera = DrivingViewCamera(self.player, self.hud, 2.2)
        self.driving_view_camera.transform_index = cam_pos_index
        self.driving_view_camera.set_sensor(driving_view_index, notify=False)

        # TODO: Set up the sensors.
        self.depth_camera = DepthCamera(self.player, self.hud, 2.2)
        self.depth_camera.transform_index = 0
        self.depth_camera.set_sensor(0, notify=False, render=False)

        actor_type = get_actor_display_name(self.player)
        self.hud.notification(actor_type)

        if self.sync:
            self.world.tick()
        else:
            self.world.wait_for_tick()
    
    def modify_vehicle_physics(self, actor):
        #If actor is not a vehicle, we cannot use the physics control
        try:
            physics_control = actor.get_physics_control()
            physics_control.use_sweep_wheel_collision = True
            actor.apply_physics_control(physics_control)
        except Exception:
            pass
    
    def tick(self, clock) -> None:
        self.hud.tick(self, clock)

    def render(self, display) -> None:
        self.driving_view_camera.render(display)
        self.hud.render(display)

    def destroy(self):
        # if self.radar_sensor is not None:
        #     self.toggle_radar()
        sensors = [
            self.driving_view_camera.sensor,
            self.depth_camera.sensor,
            
            # self.collision_sensor.sensor,
            # self.lane_invasion_sensor.sensor,
            # self.gnss_sensor.sensor,
            # self.imu_sensor.sensor
            ]
        for sensor in sensors:
            if sensor is not None:
                sensor.stop()
                sensor.destroy()
        if self.player is not None:
            self.player.destroy()

    def set_autopilot(self, enabled):
        self._autopilot_enabled = enabled
        self.player.set_autopilot(enabled)
        self.hud.notification('Autopilot %s' % ('On' if enabled else 'Off'))