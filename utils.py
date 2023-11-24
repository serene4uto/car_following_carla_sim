
def get_actor_display_name(actor, truncate=250):
    name = ' '.join(actor.type_id.replace('_', '.').title().split('.')[1:])
    return (name[:truncate - 1] + u'\u2026') if len(name) > truncate else name

def get_actor_blueprints(world, filter, generation):
    """
    Get a list of all the blueprints of the actors that can be spawned in the world.

    Parameters:
    world (carla.World object): The CARLA world to get the blueprints from.
    filter (string): The filter to apply to the blueprints. For example, "vehicle.*" will return all the blueprints of the vehicles.
    generation (string): The generation of the actors to spawn. For example, "2" will return all the blueprints of the vehicles of generation 2.

    Returns:
    bps (list of carla.ActorBlueprint objects): The list of the blueprints that match the filter and generation.
    """
    bps = world.get_blueprint_library().filter(filter)

    if generation.lower() == "all":
        return bps

    # If the filter returns only one bp, we assume that this one needed
    # and therefore, we ignore the generation
    if len(bps) == 1:
        return bps

    try:
        int_generation = int(generation)
        # Check if generation is in available generations
        if int_generation in [1, 2, 3]:
            bps = [x for x in bps if int(x.get_attribute('generation')) == int_generation]
            return bps
        else:
            print("   Warning! Actor Generation is not valid. No actor will be spawned.")
            return []
    except:
        print("   Warning! Actor Generation is not valid. No actor will be spawned.")
        return []