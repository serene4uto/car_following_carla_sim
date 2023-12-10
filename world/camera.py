import numpy as np
import pygame
import weakref

import carla
from carla import ColorConverter as cc       

class CameraManager(object):
    def __init__(self, parent_actor, hud, gamma_correction):
        self.sensor = None
        self.surface = None
        self._parent = parent_actor
        self.hud = hud
        self.recording = False

        self.transform_index = 1
        
        self._camera_transforms = None # need to be set in the subclass
        self.sensors = None # need to be set in the subclass

        self.gamma_correction = gamma_correction

        self.index = None

        # TODO: ??

    def init_sensor_spec(self, image_size):
        world = self._parent.get_world()
        bp_library = world.get_blueprint_library()
        for sensor_spec in self.sensors:
            if sensor_spec[0].startswith('sensor.camera'):
                bp = bp_library.find(sensor_spec[0])

                parent_role_name = self._parent.attributes['role_name']
                bp.set_attribute('role_name', f'{parent_role_name}/{sensor_spec[2]}')

                bp.set_attribute('image_size_x', str(image_size[0]))
                bp.set_attribute('image_size_y', str(image_size[1]))
                if bp.has_attribute('gamma'):
                    bp.set_attribute('gamma', str(self.gamma_correction))
                for attr_name, attr_value in sensor_spec[3].items():
                    bp.set_attribute(attr_name, attr_value)
                sensor_spec.append(bp)
            else:
                raise ValueError('Not Camera Sensor: %r' % sensor_spec[0])

    def toggle_camera(self):
        self.transform_index = (self.transform_index + 1) % len(self._camera_transforms)
        self.set_sensor(self.index, notify=False, force_respawn=True)

    def set_sensor(self, index, notify=True, force_respawn=False, render=True):
        index = index % len(self.sensors)
        needs_respawn = True if self.index is None else \
            (force_respawn or (self.sensors[index][2] != self.sensors[self.index][2]))
        if needs_respawn:
            if self.sensor is not None:
                self.sensor.destroy()
                self.surface = None
            self.sensor = self._parent.get_world().spawn_actor(
                self.sensors[index][-1],
                self._camera_transforms[self.transform_index][0],
                attach_to=self._parent,
                attachment_type=self._camera_transforms[self.transform_index][1])
            # We need to pass the lambda a weak reference to self to avoid
            # circular reference.
            if render:
                weak_self = weakref.ref(self)
                self.sensor.listen(lambda image: CameraManager._parse_image(weak_self, image))
        if notify:
            self.hud.notification(self.sensors[index][2])
        self.index = index

    def next_sensor(self):
        self.set_sensor(self.index + 1)

    def toggle_recording(self):
        self.recording = not self.recording
        self.hud.notification('Recording %s' % ('On' if self.recording else 'Off'))

    def render(self, display):
        if self.surface is not None:
            display.blit(self.surface, (0, 0))

    @staticmethod
    def _parse_image(weak_self, image):
        self = weak_self()
        if not self:
            return
        if self.sensors[self.index][0].startswith('sensor.camera.dvs'):
            # Example of converting the raw_data from a carla.DVSEventArray
            # sensor into a NumPy array and using it as an image
            dvs_events = np.frombuffer(image.raw_data, dtype=np.dtype([
                ('x', np.uint16), ('y', np.uint16), ('t', np.int64), ('pol', np.bool)]))
            dvs_img = np.zeros((image.height, image.width, 3), dtype=np.uint8)
            # Blue is positive, red is negative
            dvs_img[dvs_events[:]['y'], dvs_events[:]['x'], dvs_events[:]['pol'] * 2] = 255
            self.surface = pygame.surfarray.make_surface(dvs_img.swapaxes(0, 1))
        elif self.sensors[self.index][0].startswith('sensor.camera.optical_flow'):
            image = image.get_color_coded_flow()
            array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
            array = np.reshape(array, (image.height, image.width, 4))
            array = array[:, :, :3]
            array = array[:, :, ::-1]
            self.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
        else:
            image.convert(self.sensors[self.index][1])
            array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
            array = np.reshape(array, (image.height, image.width, 4))
            array = array[:, :, :3]
            array = array[:, :, ::-1]
            self.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame)




class DrivingViewCamera(CameraManager):
    def __init__(self, parent_actor, hud, gamma_correction):
        super().__init__(parent_actor, hud, gamma_correction)

        bound_x = 0.5 + self._parent.bounding_box.extent.x
        bound_y = 0.5 + self._parent.bounding_box.extent.y
        bound_z = 0.5 + self._parent.bounding_box.extent.z
        Attachment = carla.AttachmentType

        # Define Driving View Positions
        self._camera_transforms = [
            # (carla.Transform(carla.Location(x=+0.8*bound_x, y=+0.0*bound_y, z=1.3*bound_z)), Attachment.Rigid),
            (carla.Transform(carla.Location(x=+(0.2)*bound_x, y=-0.25*bound_y, z=1*bound_z), ), Attachment.Rigid),
            (carla.Transform(carla.Location(x=+(0.2)*bound_x, y=+0.0*bound_y, z=1*bound_z), ), Attachment.Rigid),
            (carla.Transform(carla.Location(x=+(-0.0)*bound_x, y=-0.25*bound_y, z=1*bound_z), ), Attachment.Rigid),
            (carla.Transform(carla.Location(x=-2.0*bound_x, y=+0.0*bound_y, z=2.0*bound_z), carla.Rotation(pitch=8.0)), Attachment.SpringArmGhost),
            (carla.Transform(carla.Location(x=bound_x + 0.05, z=bound_z+0.05), carla.Rotation(pitch=5)), Attachment.Rigid),
            
        ]

        # Define Sensors for Driving View
        self.sensors = [
            ['sensor.camera.rgb', cc.Raw, 'RGBCamera_Windshield', {
                'fov': '120',
            }],
        ]

        self.init_sensor_spec(image_size=(self.hud.dim[0], self.hud.dim[1]))


class DepthCamera(CameraManager):
    def __init__(self, parent_actor, hud, gamma_correction, sensor_name):
        super().__init__(parent_actor, hud, gamma_correction)

        bound_x = 0.5 + self._parent.bounding_box.extent.x
        bound_y = 0.5 + self._parent.bounding_box.extent.y
        bound_z = 0.5 + self._parent.bounding_box.extent.z
        Attachment = carla.AttachmentType

        # Define Camera Positions
        self._camera_transforms = [
            (carla.Transform(carla.Location(x=+0.8*bound_x  , y=+0.0*bound_y   , z=+1.3*bound_z), ), Attachment.Rigid),
            (carla.Transform(carla.Location(x=+(0.2)*bound_x, y=-0.25*bound_y, z=+1*bound_z), ), Attachment.Rigid),
        ]

        # Define Sensors for Camera
        self.sensors = [
            ['sensor.camera.depth', cc.Raw, sensor_name, {}],
        ]


        self.init_sensor_spec(image_size=(1280, 720))
        

