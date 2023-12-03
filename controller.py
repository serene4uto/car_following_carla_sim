import carla
import pygame
from pygame import locals as lc
from configparser import ConfigParser
import math

class InputControl(object):
    def __init__(self, world, start_in_autopilot):
        """ Initialize the input controller """
        self._world = world

        self._autopilot_enabled = start_in_autopilot
        self._ackermann_enabled = False
        self._ackermann_reverse = 1
        if isinstance(world.player, carla.Vehicle):
            self._control = carla.VehicleControl()
            self._ackermann_control = carla.VehicleAckermannControl()
            self._lights = carla.VehicleLightState.NONE
            world.player.set_autopilot(self._autopilot_enabled)
            world.player.set_light_state(self._lights)
        elif isinstance(world.player, carla.Walker):
            self._control = carla.WalkerControl()
            self._autopilot_enabled = False
            self._rotation = world.player.get_transform().rotation
        else:
            raise NotImplementedError("Actor type not supported")
        self._steer_cache = 0.0
        self._world.hud.notification("Press 'H' or '?' for help.", seconds=4.0)
    

    def parse_events(self):
        """ Parse the input events and send the commands to the vehicle """
        raise NotImplementedError()
    
    def _hud_toggle_info(self):
        self._world.hud.toggle_info()
    
    def _hud_toggle_help(self):
        #TODO: implement this
        pass
    
    def _hud_toggle_driving_view(self):
        self._world.driving_view_camera.toggle_camera()

    def _control_vehicle_toggle_autopilot(self, sync_mode):
        if not self._autopilot_enabled and not sync_mode:
            print("WARNING: You are currently in asynchronous mode and could "
                    "experience some issues with the traffic simulation")
            self._autopilot_enabled = not self._autopilot_enabled
            self._world.player.set_autopilot(self._autopilot_enabled)
            self._world.hud.notification(
                'Autopilot %s' % ('On' if self._autopilot_enabled else 'Off'))
            
    def _control_vehicle_toggle_ackermann_controller(self):
        self._ackermann_enabled = not self._ackermann_enabled
        self._world.hud.show_ackermann_info(self._ackermann_enabled)
        self._world.hud.notification("Ackermann Controller %s" %
                ("Enabled" if self._ackermann_enabled else "Disabled"))
        
    ''' Vehicle Gearbox Control '''
    def _control_vehicle_toggle_manual_gear_shift(self):
        self._control.manual_gear_shift = not self._control.manual_gear_shift
        self._control.gear = self._world.player.get_control().gear
        self._world.hud.notification('%s Transmission' %
                ('Manual' if self._control.manual_gear_shift else 'Automatic'))
        
    def _control_vehicle_manual_gear_down(self):
        if self._control.manual_gear_shift:
            self._control.gear = min(1, self._control.gear + 1)
    
    def _control_vehicle_manual_gear_up(self):
        if self._control.manual_gear_shift:
            self._control.gear = self._control.gear + 1
    
    def _control_vehicle_toggle_reverse(self):
        if not self._ackermann_enabled:
            self._control.gear = 1 if self._control.reverse else -1
        else:
            self._ackermann_reverse *= -1
            # Reset ackermann control
            self._ackermann_control = carla.VehicleAckermannControl()
    
    ''' Vehicle Lights Control '''
    def _control_vehicle_toggle_light_special(self, current_lights):
        current_lights ^= carla.VehicleLightState.Special1
        return current_lights
    
    def _control_vehicle_toggle_light_high_beam(self):
        current_lights ^= carla.VehicleLightState.HighBeam
        return current_lights
    
    def _control_vehicle_switch_lights(self, current_lights):
        # closed -> position -> low beam -> fog
        if not current_lights & carla.VehicleLightState.Position:
            self._world.hud.notification("Position lights")
            current_lights |= carla.VehicleLightState.Position
        else:
            self._world.hud.notification("Low beam lights")
            current_lights |= carla.VehicleLightState.LowBeam
        if current_lights & carla.VehicleLightState.LowBeam:
            self._world.hud.notification("Fog lights")
            current_lights |= carla.VehicleLightState.Fog
        if current_lights & carla.VehicleLightState.Fog:
            self._world.hud.notification("Lights off")
            current_lights ^= carla.VehicleLightState.Position
            current_lights ^= carla.VehicleLightState.LowBeam
            current_lights ^= carla.VehicleLightState.Fog
        return current_lights
    
    def _control_vehicle_toggle_light_interior(self):
        current_lights ^= carla.VehicleLightState.Interior
        return current_lights
    
    def _control_vehicle_toggle_light_left_blinker(self):
        current_lights ^= carla.VehicleLightState.LeftBlinker
        return current_lights
    
    def _control_vehicle_toggle_light_right_blinker(self):
        current_lights ^= carla.VehicleLightState.RightBlinker
        return current_lights
    
    ''' Vehicle Driving Control '''
    # def _control_vehicle_throttle_up(self):
    #     if not self._ackermann_enabled:
    #         self._control.throttle = min(self._control.throttle + 0.1, 1.00)
    #     else:
    #         self._ackermann_control.speed += round(0.005, 2) * self._ackermann_reverse
    
    # def _control_vehicle_throttle_down(self):
    #     if not self._ackermann_enabled:
    #         self._control.throttle = 0.0
    
    # def _control_vehicle_brake_up(self):
    #     if not self._ackermann_enabled:
    #         self._control.brake = min(self._control.brake + 0.2, 1)
    #     else:
    #         self._ackermann_control.speed -= min(abs(self._ackermann_control.speed), round(0.005, 2)) * self._ackermann_reverse
    #         self._ackermann_control.speed = max(0, abs(self._ackermann_control.speed)) * self._ackermann_reverse
    
    # def _control_vehicle_brake_down(self):
    #     if not self._ackermann_enabled:
    #         self._control.brake = 0
    
    # def _control_vehicle_steer_by_key(self, milliseconds, isleft):
    #     steer_increment = 5e-4 * milliseconds
    #     if isleft:
    #         if self._steer_cache > 0:
    #             self._steer_cache = 0
    #         else:
    #             self._steer_cache -= steer_increment
    #     else:
    #         if self._steer_cache < 0:
    #             self._steer_cache = 0
    #         else:
    #             self._steer_cache += steer_increment


        

class KeyboardControl(InputControl):
    def __init__(self, world, start_in_autopilot):
        super().__init__(world, start_in_autopilot)

        #TODO: Define the key mapping

    def parse_events(self, clock, sync_mode):
        """ Parse the keyboard events and send the commands to the vehicle """

        if isinstance(self._control, carla.VehicleControl):
            current_lights = self._lights

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            elif event.type == pygame.KEYUP:
                if self._is_quit_shortcut(event.key):
                    return True
                elif event.key == lc.K_F1:
                    self._hud_toggle_info()

                # elif event.key == lc.K_h or (event.key == lc.K_SLASH and pygame.key.get_mods() & lc.KMOD_SHIFT):
                #     self._hud_toggle_help()

                elif event.key == lc.K_TAB:
                    self._hud_toggle_driving_view()
                
                if isinstance(self._control, carla.VehicleControl):
                    if event.key == lc.K_f:
                        # Toggle ackermann controller                      
                        self._control_vehicle_toggle_ackermann_controller()
                    if event.key == lc.K_q:
                        self._control_vehicle_toggle_reverse()
                    elif event.key == lc.K_m:
                        self._control_vehicle_toggle_manual_gear_shift()
                    elif event.key == lc.K_COMMA:
                        self._control_vehicle_manual_gear_down()
                    elif event.key == lc.K_PERIOD:
                        self._control_vehicle_manual_gear_up()
                    elif event.key == lc.K_p and not pygame.key.get_mods() & lc.KMOD_CTRL:
                        self._control_vehicle_toggle_autopilot(sync_mode)
                    
                    #TODO: Define the key mapping for vehicle lights control
                    # elif event.key == lc.K_l and pygame.key.get_mods() & lc.KMOD_CTRL:
                    #     current_lights ^= carla.VehicleLightState.Special1
                    # elif event.key == lc.K_l and pygame.key.get_mods() & lc.KMOD_SHIFT:
                    #     current_lights ^= carla.VehicleLightState.HighBeam
                    # elif event.key == lc.K_l:
                    #     # Use 'L' key to switch between lights:
                    #     # closed -> position -> low beam -> fog
                    #     if not self._lights & carla.VehicleLightState.Position:
                    #         world.hud.notification("Position lights")
                    #         current_lights |= carla.VehicleLightState.Position
                    #     else:
                    #         world.hud.notification("Low beam lights")
                    #         current_lights |= carla.VehicleLightState.LowBeam
                    #     if self._lights & carla.VehicleLightState.LowBeam:
                    #         world.hud.notification("Fog lights")
                    #         current_lights |= carla.VehicleLightState.Fog
                    #     if self._lights & carla.VehicleLightState.Fog:
                    #         world.hud.notification("Lights off")
                    #         current_lights ^= carla.VehicleLightState.Position
                    #         current_lights ^= carla.VehicleLightState.LowBeam
                    #         current_lights ^= carla.VehicleLightState.Fog
                    # elif event.key == lc.K_i:
                    #     current_lights ^= carla.VehicleLightState.Interior
                    # elif event.key == lc.K_z:
                    #     current_lights ^= carla.VehicleLightState.LeftBlinker
                    # elif event.key == lc.K_x:
                    #     current_lights ^= carla.VehicleLightState.RightBlinker
            
        if not self._autopilot_enabled:
            if isinstance(self._control, carla.VehicleControl):
                self._parse_vehicle_keys(pygame.key.get_pressed(), clock.get_time())
                self._control.reverse = self._control.gear < 0

                # Set automatic control-related vehicle lights
                # if self._control.brake:
                #     current_lights |= carla.VehicleLightState.Brake
                # else: # Remove the Brake flag
                #     current_lights &= ~carla.VehicleLightState.Brake
                # if self._control.reverse:
                #     current_lights |= carla.VehicleLightState.Reverse
                # else: # Remove the Reverse flag
                #     current_lights &= ~carla.VehicleLightState.Reverse
                # if current_lights != self._lights: # Change the light state only if necessary
                #     self._lights = current_lights
                #     self._world.player.set_light_state(carla.VehicleLightState(self._lights))

                # Apply control
                if not self._ackermann_enabled:
                    self._world.player.apply_control(self._control)
                else:
                    self._world.player.apply_ackermann_control(self._ackermann_control)
                    # Update control to the last one applied by the ackermann controller.
                    self._control = self._world.player.get_control()
                    # Update hud with the newest ackermann control
                    self._world.hud.update_ackermann_control(self._ackermann_control)

        elif isinstance(self._control, carla.WalkerControl):
            self._parse_walker_keys(pygame.key.get_pressed(), clock.get_time(), self._world)
            self._world.player.apply_control(self._control)
    
    
    def _parse_vehicle_keys(self, keys, milliseconds):
        if keys[lc.K_UP] or keys[lc.K_w]:
            if not self._ackermann_enabled:
                self._control.throttle = min(self._control.throttle + 0.1, 1.00)
            else:
                self._ackermann_control.speed += round(milliseconds * 0.005, 2) * self._ackermann_reverse
        else:
            if not self._ackermann_enabled:
                self._control.throttle = 0.0

        if keys[lc.K_DOWN] or keys[lc.K_s]:
            if not self._ackermann_enabled:
                self._control.brake = min(self._control.brake + 0.2, 1)
            else:
                self._ackermann_control.speed -= min(abs(self._ackermann_control.speed), round(milliseconds * 0.005, 2)) * self._ackermann_reverse
                self._ackermann_control.speed = max(0, abs(self._ackermann_control.speed)) * self._ackermann_reverse
        else:
            if not self._ackermann_enabled:
                self._control.brake = 0

        steer_increment = 5e-4 * milliseconds
        if keys[lc.K_LEFT] or keys[lc.K_a]:
            if self._steer_cache > 0:
                self._steer_cache = 0
            else:
                self._steer_cache -= steer_increment
        elif keys[lc.K_RIGHT] or keys[lc.K_d]:
            if self._steer_cache < 0:
                self._steer_cache = 0
            else:
                self._steer_cache += steer_increment
        else:
            self._steer_cache = 0.0
        self._steer_cache = min(0.7, max(-0.7, self._steer_cache))
        if not self._ackermann_enabled:
            self._control.steer = round(self._steer_cache, 1)
            self._control.hand_brake = keys[lc.K_SPACE]
        else:
            self._ackermann_control.steer = round(self._steer_cache, 1)

    def _parse_walker_keys(self, keys, milliseconds, world):
        self._control.speed = 0.0
        if keys[lc.K_DOWN] or keys[lc.K_s]:
            self._control.speed = 0.0
        if keys[lc.K_LEFT] or keys[lc.K_a]:
            self._control.speed = .01
            self._rotation.yaw -= 0.08 * milliseconds
        if keys[lc.K_RIGHT] or keys[lc.K_d]:
            self._control.speed = .01
            self._rotation.yaw += 0.08 * milliseconds
        if keys[lc.K_UP] or keys[lc.K_w]:
            self._control.speed = world.player_max_speed_fast if pygame.key.get_mods() & lc.KMOD_SHIFT else world.player_max_speed
        self._control.jump = keys[lc.K_SPACE]
        self._rotation.yaw = round(self._rotation.yaw, 1)
        self._control.direction = self._rotation.get_forward_vector()


    
    @staticmethod
    def _is_quit_shortcut(key):
        return (key == lc.K_ESCAPE) or (key == lc.K_q and pygame.key.get_mods() & lc.KMOD_CTRL)
    


class SteeringWheelControl(InputControl):
    def __init__(self, world, start_in_autopilot, config_file='steering_wheel_default.ini'):
        super().__init__(world, start_in_autopilot)
    
        # initialize steering wheel
        pygame.joystick.init()

        joystick_count = pygame.joystick.get_count()
        if joystick_count > 1:
            raise ValueError("Please Connect Just One Joystick")
        
        self._joystick = pygame.joystick.Joystick(0)
        self._joystick.init()

        self._parser = ConfigParser()
        self._parser.read(config_file)
        self._steer_axis_idx = int(
            self._parser.get('G29 Racing Wheel', 'steering_wheel_axis'))
        self._throttle_axis_idx = int(
            self._parser.get('G29 Pedals', 'throttle_axis'))
        self._brake_axis_idx = int(
            self._parser.get('G29 Pedals', 'brake_axis'))
        
        self._reverse_button_idx = int(
            self._parser.get('G29 Racing Wheel', 'reverse_button'))
        
        self._handbrake_button_idx = int(
            self._parser.get('G29 Racing Wheel', 'handbrake_button'))
        
        print("Steering Wheel Control Initialized")
        print("Steering Wheel Axis Index: ", self._steer_axis_idx)
        print("Throttle Axis Index: ", self._throttle_axis_idx)
        print("Brake Axis Index: ", self._brake_axis_idx)
        print("Reverse Button Index: ", self._reverse_button_idx)
        print("Handbrake Button Index: ", self._handbrake_button_idx)
        
        #TODO: support manual gear shift

    def parse_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == self._reverse_button_idx:
                    self._control_vehicle_toggle_reverse()
        
        if not self._autopilot_enabled:
            if isinstance(self._control, carla.VehicleControl):
                self._parse_vehicle_wheel()
                self._control.reverse = self._control.gear < 0
            self._world.player.apply_control(self._control)
        
    

    def _parse_vehicle_wheel(self):
        numAxes = self._joystick.get_numaxes()
        jsInputs = [float(self._joystick.get_axis(i)) for i in range(numAxes)]
        # print (jsInputs)
        jsButtons = [float(self._joystick.get_button(i)) for i in
                     range(self._joystick.get_numbuttons())]

        # Custom function to map range of inputs [1, -1] to outputs [0, 1] i.e 1 from inputs means nothing is pressed
        # For the steering, it seems fine as it is
        K1 = 1.0  # 0.55
        steerCmd = K1 * math.tan(1.1 * jsInputs[self._steer_axis_idx])

        # For the throttle and brake, we need to map the range [-1, 1] to [0, 1]
        throttleCmd = (jsInputs[self._throttle_axis_idx] + 1) /2
        if throttleCmd <= 0:
            throttleCmd = 0
        elif throttleCmd > 1:
            throttleCmd = 1

        brakeCmd = (jsInputs[self._brake_axis_idx] + 1) /2
        if brakeCmd <= 0:
            brakeCmd = 0
        elif brakeCmd > 1:
            brakeCmd = 1

        # print("Steer: ", steerCmd, "Throttle: ", throttleCmd, "Brake: ", brakeCmd)

        self._control.steer = steerCmd
        self._control.brake = brakeCmd
        self._control.throttle = throttleCmd

        self._control.hand_brake = bool(jsButtons[self._handbrake_button_idx])
            

                
        
        



                
                
                
                





