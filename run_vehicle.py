
import argparse
import logging

import random
import pygame
import carla
import sys
from hud import HUD

import yaml

import time

from controller.vehicle_controller import VehicleController
from world.vehicle_world import VehicleWorld

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
        '--rolename',
        metavar='NAME',
        default='hero',
        help='actor role name (default: "hero")')
    argparser.add_argument(
        '--spawn_point_idx',
        default=None,
        type=int,
        help='spawn point index (default: None --> random)')
    
    return argparser.parse_args()



def gameloop(args):
    pygame.init()
    pygame.font.init()
    ego_world = None
    original_settings = None
    preceding_vehicle = None

    # Read Input Control Cfg
    with open('config/steering_wheel_default.yaml', 'r') as f:
        js_cfg = yaml.load(f, Loader=yaml.FullLoader)

    with open('config/keyboard_default.yaml', 'r') as f:
        kb_cfg = yaml.load(f, Loader=yaml.FullLoader)

    # Start Carla Client
    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(10.0)
        sim_world = client.get_world()

        # Setting for world
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

        # Init HUD and World for Ego Vehicle
        hud = HUD(args.width, args.height)
        ego_world = VehicleWorld(sim_world, hud, 
                                args.sync, args.rolename, args.spawn_point_idx,
                                args.filter)
        v_controller = VehicleController(ego_world, args.autopilot, 
                                         js_cfg=js_cfg, kb_cfg=kb_cfg)
        
        # Init for Preceding Vehicle


        if args.sync:
            sim_world.tick()
        else:
            sim_world.wait_for_tick()

        clock = pygame.time.Clock()


        # time.sleep(10)



        # Instanciating the vehicle to which we attached the sensors
        bp = sim_world.get_blueprint_library().filter('charger_2020')[0]
        preceding_vehicle = sim_world.try_spawn_actor(bp, sim_world.get_map().get_spawn_points()[1])
        preceding_vehicle.set_autopilot(True)
        



        while True:
            if args.sync:
                sim_world.tick()
            clock.tick_busy_loop(60)

            #TODO: Check Input Signal from Controller
            if v_controller.parse_events():
                return
            

            ego_world.tick(clock)
            ego_world.render(display)
            pygame.display.flip()
 

    finally:
        if original_settings:
            sim_world.apply_settings(original_settings)

        if ego_world is not None:
            ego_world.destroy()
            preceding_vehicle.destroy()


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



