def test_code():
    while (time.time() - start_time) < period + stopping_time:
        while pedestrian_observed():
            stop() # Stop the vehicle if a pedestrian is observed
            if not pedestrian_observed() and pedestrian_observed():
                stop()
            elif pedestrian_observed():
                stop()
            else:
                velocity_publisher()
        velocity_publisher(linear, angular) # Publish the velocity commands