import carla
import pygame
import pygame.locals as pgl

import math

import logging

def s2k(key_str):
    return eval(f'pgl.{key_str}')

class VehicleController(object):
    def __init__(self, vehicle_world, start_in_autopilot,
                 js_cfg, kb_cfg):
        self._vehicle_world = vehicle_world
        self._autopilot_enabled = start_in_autopilot
        self._ackermann_enabled = False
        self._ackermann_reverse = 1

        if isinstance(self._vehicle_world.player, carla.Vehicle):
            self._control = carla.VehicleControl()
            self._ackermann_control = carla.VehicleAckermannControl()
            self._lights = carla.VehicleLightState.NONE
            self._vehicle_world.player.set_autopilot(self._autopilot_enabled)
            self._vehicle_world.player.set_light_state(self._lights)
        else:
            raise NotImplementedError("Only Vehicle is supported")
        
        self.steer = 0.0

        # self._vehicle_world.hud.notification("Press 'H' or '?' for help.", seconds=4.0)


        self.kb_cfg = kb_cfg
        self.js_cfg = js_cfg

        # initialize joy stick devices
        pygame.joystick.init()
        
        joystick_count = pygame.joystick.get_count()
        if joystick_count > 1:
            raise ValueError("Please Connect Just One Joystick")
        
        self._joystick = pygame.joystick.Joystick(0)
        self._joystick.init()




    @staticmethod
    def _is_quit_shortcut(key):
        pass

    def _control_vehicle_toggle_reverse(self):
        if not self._ackermann_enabled:
            self._control.gear = 1 if self._control.reverse else -1
        else:
            self._ackermann_reverse *= -1
            # Reset ackermann control
            self._ackermann_control = carla.VehicleAckermannControl()

    
    def parse_events(self, clock, sync_mode):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
        
            # joystick events
            elif event.type == pygame.JOYBUTTONDOWN:

                # Toggle Reverse
                if event.button == self.js_cfg['reverse_button']:
                    self._control_vehicle_toggle_reverse()

                    
            # keyboard events
            elif event.type == pygame.KEYDOWN:
                if event.key == s2k(self.kb_cfg['reverse_key']):
                    self._control_vehicle_toggle_reverse()

                

                
        if not self._autopilot_enabled:
            # self._parse_vehicle_keys(pygame.key.get_pressed(), clock.get_time())
            self._parse_vehicle_wheel()
            self._control.reverse = self._control.gear < 0
            self._vehicle_world.player.apply_control(self._control)
    

            
    def _parse_vehicle_keys(self, keys, milliseconds):
        if keys[s2k(self.kb_cfg['throttle_key'])]:
            if not self._ackermann_enabled:
                self._control.throttle = min(self._control.throttle + 0.1, 1.00)
            else:
                self._ackermann_control.speed += round(milliseconds * 0.005, 2) * self._ackermann_reverse
        else:
            if not self._ackermann_enabled:
                self._control.throttle = 0.0

        if keys[s2k(self.kb_cfg['brake_key'])]:
            if not self._ackermann_enabled:
                self._control.brake = min(self._control.brake + 0.2, 1)
            else:
                self._ackermann_control.speed -= min(abs(self._ackermann_control.speed), round(milliseconds * 0.005, 2)) * self._ackermann_reverse
                self._ackermann_control.speed = max(0, abs(self._ackermann_control.speed)) * self._ackermann_reverse
        else:
            if not self._ackermann_enabled:
                self._control.brake = 0

        steer_increment = 5e-4 * milliseconds
        if keys[s2k(self.kb_cfg['steer_left_key'])]:
            if self._steer_cache > 0:
                self._steer_cache = 0
            else:
                self._steer_cache -= steer_increment
        elif keys[s2k(self.kb_cfg['steer_right_key'])]:
            if self._steer_cache < 0:
                self._steer_cache = 0
            else:
                self._steer_cache += steer_increment
        else:
            self._steer_cache = 0.0
        self._steer_cache = min(0.7, max(-0.7, self._steer_cache))
        if not self._ackermann_enabled:
            self._control.steer = round(self._steer_cache, 1)
            self._control.hand_brake = keys[s2k(self.kb_cfg['handbrake_key'])]
        else:
            self._ackermann_control.steer = round(self._steer_cache, 1)

    def _parse_vehicle_wheel(self):
        numAxes = self._joystick.get_numaxes()
        jsInputs = [float(self._joystick.get_axis(i)) for i in range(numAxes)]
        # print (jsInputs)
        jsButtons = [float(self._joystick.get_button(i)) for i in
                     range(self._joystick.get_numbuttons())]

        # Custom function to map range of inputs [1, -1] to outputs [0, 1] i.e 1 from inputs means nothing is pressed
        # For the steering, it seems fine as it is
        K1 = 1.0  # 0.55
        steerCmd = K1 * math.tan(1.1 * jsInputs[self.js_cfg['steer_axis']])

        K2 = 1.6  # 1.6
        throttleCmd = K2 + (2.05 * math.log10(
            -0.7 * jsInputs[self.js_cfg['throttle_axis']] + 1.4) - 1.2) / 0.92
        if throttleCmd <= 0:
            throttleCmd = 0
        elif throttleCmd > 1:
            throttleCmd = 1

        brakeCmd = 1.6 + (2.05 * math.log10(
            -0.7 * jsInputs[self.js_cfg['brake_axis']] + 1.4) - 1.2) / 0.92
        if brakeCmd <= 0:
            brakeCmd = 0
        elif brakeCmd > 1:
            brakeCmd = 1

        # print("Steer: ", steerCmd, "Throttle: ", throttleCmd, "Brake: ", brakeCmd)

        self._control.steer = steerCmd
        self._control.brake = brakeCmd
        self._control.throttle = throttleCmd

        self._control.hand_brake = bool(jsButtons[self.js_cfg['handbrake_button']])
                




