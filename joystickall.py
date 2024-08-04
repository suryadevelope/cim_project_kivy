import pygame
import time

# Initialize Pygame
pygame.init()

# Initialize the joystick module
pygame.joystick.init()

# Check for joystick count
joystick_count = pygame.joystick.get_count()
if joystick_count == 0:
    print("No joystick connected.")
    pygame.quit()
    exit()

# Use the first connected joystick
joystick = pygame.joystick.Joystick(0)
joystick.init()

# Get joystick information
name = joystick.get_name()
axes = joystick.get_numaxes()
buttons = joystick.get_numbuttons()
hats = joystick.get_numhats()

print(f"Joystick Name: {name}")
print(f"Number of Axes: {axes}")
print(f"Number of Buttons: {buttons}")
print(f"Number of Hats: {hats}")





# Function to print joystick state
def print_joystick_state():
    # Read axis values
    for i in range(axes):
        axis = joystick.get_axis(i)
        print(f"Axis {i} value: {axis:.3f}")

    # # Read button states
    for i in range(buttons):
        button = joystick.get_button(i)
        print(f"Button {i} state: {button}")

    # Read hat (D-pad) states
    for i in range(hats):
        hat = joystick.get_hat(i)
        print(f"Hat {i} state: {hat}")

# Main loop to continuously print joystick state
try:
    while True:
        # Pump Pygame event queue to handle joystick events
        pygame.event.pump()

        # Print joystick state
        print_joystick_state()

        # Delay for a short period to avoid spamming output
        time.sleep(0.5)
        print("-----")

except KeyboardInterrupt:
    print("Exiting...")

finally:
    # Quit Pygame
    pygame.quit()
