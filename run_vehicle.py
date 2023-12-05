
import argparse
import logging

import random
import pygame
import carla
import sys
from hud import HUD
from camera import DrivingViewCamera, DepthCamera

# from controller import KeyboardControl
# from controller import SteeringWheelControl
# from old_controller import KeyboardControl

from controller.vehicle_controller import VehicleController

from utils import get_actor_blueprints, get_actor_display_name

def argparser():
    argparser = argparse.ArgumentParser(
        description='CARLA experiment vehicle control')
    
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')
    argparser.add_argument(
        '--sync',
        action='store_true',
        help='Activate synchronous mode execution')
    argparser.add_argument(
        '-a', '--autopilot',
        action='store_true',
        help='enable autopilot')
    argparser.add_argument(
        '--filter',
        metavar='PATTERN',
        default='vehicle.*',
        help='actor filter (default: "vehicle.*")')
    argparser.add_argument(
        '--generation',
        metavar='G',
        default='2',
        help='restrict to certain actor generation (values: "1","2","All" - default: "2")')
    argparser.add_argument(
        '--rolename',
        metavar='NAME',
        default='hero',
        help='actor role name (default: "hero")')
    argparser.add_argument(
        '--gamma',
        default=2.2,
        type=float,
        help='Gamma correction of the camera (default: 2.2)')
    argparser.add_argument(
        '--spawn_point_idx',
        default=None,
        type=int,
        help='spawn point index (default: None --> random)')
    
    return argparser.parse_args()


class World(object):
    def __init__(self, carla_world, hud, args) -> None:
        self.world = carla_world
        self.sync = args.sync
        self.actor_role_name = args.rolename
        self.spawn_point_idx = args.spawn_point_idx

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

        self._actor_filter = args.filter
        self._actor_generation = args.generation
        self._gamma = args.gamma

        self.player_max_speed = 1.589
        self.player_max_speed_fast = 3.713

        self.restart()

        self.world.on_tick(hud.on_world_tick) # Register the tick function of the hud to the world tick event.



    def restart(self) -> None:
        self.player_max_speed = 1.589
        self.player_max_speed_fast = 3.713
        
        # Keep same driving view camera config if already exists.
        driving_view_index = self.driving_view_camera.index if self.driving_view_camera is not None else 0
        cam_pos_index = self.driving_view_camera.transform_index if self.driving_view_camera is not None else 0

        # Get a vehicle blueprint and set parameters.
        blueprint_list = get_actor_blueprints(self.world, self._actor_filter, self._actor_generation)
        if not blueprint_list:
            raise ValueError("Couldn't find any blueprints with the specified filters")
        
        blueprint = blueprint_list[0] # Select the first blueprint (Mercedes-Benz C-Class). TODO: Make this configurable.

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
        
        # set the max speed
        if blueprint.has_attribute('speed'):
            self.player_max_speed = float(blueprint.get_attribute('speed').recommended_values[1])
            self.player_max_speed_fast = float(blueprint.get_attribute('speed').recommended_values[2])

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
        self.driving_view_camera = DrivingViewCamera(self.player, self.hud, self._gamma)
        self.driving_view_camera.transform_index = cam_pos_index
        self.driving_view_camera.set_sensor(driving_view_index, notify=False)

        # TODO: Set up the sensors.
        self.depth_sensor_camera = DepthCamera(self.player, self.hud, self._gamma)
        self.depth_sensor_camera.transform_index = 0
        self.depth_sensor_camera.set_sensor(0, notify=False)

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



def gameloop(args):
    pygame.init()
    pygame.font.init()
    world = None
    original_settings = None

    leading_car = None

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2000.0)
        sim_world = client.get_world()
        if args.sync:
            original_settings = sim_world.get_settings()
            settings = sim_world.get_settings()
            if not settings.synchronous_mode:
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 0.05
            sim_world.apply_settings(settings)

            traffic_manager = client.get_trafficmanager()
            traffic_manager.set_synchronous_mode(True)

        if args.autopilot and not sim_world.get_settings().synchronous_mode:
            print("WARNING: You are currently in asynchronous mode and could "
                  "experience some issues with the traffic simulation")
        
        display = pygame.display.set_mode(
            (args.width, args.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF)
        display.fill((0,0,0))
        pygame.display.flip()

        hud = HUD(args.width, args.height)
        world = World(sim_world, hud, args)
        v_controller = VehicleController(world, args.autopilot, 
                                         js_cfg_yaml='config/steering_wheel_default.yaml', 
                                         kb_cfg_yaml='config/keyboard_default.yaml')


        if args.sync:
            sim_world.tick()
        else:
            sim_world.wait_for_tick()

        clock = pygame.time.Clock()



        # Instanciating the vehicle to which we attached the sensors
        bp = sim_world.get_blueprint_library().filter('charger_2020')[0]
        leading_car = sim_world.try_spawn_actor(bp, sim_world.get_map().get_spawn_points()[1])
        leading_car.set_autopilot(True)



        while True:
            if args.sync:
                sim_world.tick()
            clock.tick_busy_loop(60)

            #TODO: Check Input Signal from Controller
            if v_controller.parse_events(clock, args.sync):
                return

            world.tick(clock)
            world.render(display)
            pygame.display.flip()
 

    finally:
        if original_settings:
            sim_world.apply_settings(original_settings)

        if world is not None:
            world.destroy()

            # carla.command.DestroyActor(leading_car)


        pygame.quit()



def main():
    args = argparser()

    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        gameloop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')



if __name__ == "__main__":
    main()



