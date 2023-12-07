import carla
import pygame
import numpy as np
from carla import ColorConverter as cc    
import queue

render_queue = queue.Queue()    

def parse_image(image):
    image.convert(cc.Raw)
    array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
    array = np.reshape(array, (image.height, image.width, 4))
    array = array[:, :, :3]
    array = array[:, :, ::-1]
    surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
    render_queue.put(surface)

if __name__ == '__main__':
    pygame.init()
    pygame.font.init()
    test_actor_world  = None

    try:
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(2000.0)
        sim_world = client.get_world()

        display = pygame.display.set_mode(
        (1280, 720),
            pygame.HWSURFACE | pygame.DOUBLEBUF)
        display.fill((0,0,0))
        pygame.display.flip()


        sim_world.wait_for_tick()

        sensors = sim_world.get_actors().filter('sensor.*')
        monitored_sensors = None

        for sensor in sensors:
            if sensor.attributes['role_name'] == 'hero/Windshield Camera RGB':
                monitored_sensor = sensor
        
        monitored_sensor.listen(lambda image: parse_image(image))

        while True:
            
            if not render_queue.empty():
                display.blit(render_queue.get(), (0,0))
            pygame.display.flip()


    
    finally:

        pygame.quit()