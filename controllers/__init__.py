import Leap
from controllers import gestures
from filters import (MixedFilter, NoiseFilter, LowpassFilter)
from communication import send_command

class ObjectController(Leap.Listener):
    def __init__(self):
        super(ObjectController, self).__init__()

        self.nb_hands = MixedFilter([
            NoiseFilter(10, 0.3, 10),
            LowpassFilter(0.5)])

        # grab stuff
        self.opening_hand = gestures.OpeningHand()
        self.closing_hand = gestures.ClosingHand()
        self.is_grabbing = False

        # scale stuff
        self.scale_opening_hands = (gestures.OpeningHand(), gestures.OpeningHand())
        self.scale_closing_hands = (gestures.ClosingHand(), gestures.ClosingHand())
        self.is_scaling = False

        # hand location
        self.loc_x_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05)])
        self.loc_y_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05)])
        self.loc_z_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05)])

        self.loc_x_origin = 0
        self.loc_y_origin = 0
        self.loc_z_origin = 0

        # hand rotation
        self.rot_x_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05) ])
        self.rot_y_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05) ])
        self.rot_z_hand = MixedFilter([
            NoiseFilter(1000, 100, 20),
            LowpassFilter(0.05) ])

        self.rot_x_origin = 0
        self.rot_y_origin = 0
        self.rot_z_origin = 0

    def on_init(self, controller):
        pass

    def on_exit(self, controller):
        pass

    def on_frame(self, controller):
        frame = controller.frame()
        self.nb_hands.add_value(len(frame.hands))

        # need about 1 hand
        if self.nb_hands.around(1, 0.1):
            self.try_grab(frame)
        elif self.nb_hands.around(2, 0.1):
            self.try_scale(frame)
        else:
            self.reset_grab()
            self.reset_scale()

    # scale interface

    def try_scale(self, frame):
        first_hand, second_hand = frame.hands[0], frame.hands[1]
        self.scale_closing_hands[0].frame(first_hand)
        self.scale_opening_hands[0].frame(first_hand)
        self.scale_closing_hands[1].frame(second_hand)
        self.scale_opening_hands[1].frame(second_hand)

        # start scaling
        if not self.is_scaling:
            #print 'Hand', first_hand.id, 'closed:', self.scale_closing_hands[0].is_done()
            #print 'Hand', second_hand.id, 'closed:', self.scale_closing_hands[1].is_done()
            if all(ch.is_done() for ch in self.scale_closing_hands):
                self.start_scaling(first_hand, second_hand)
        else:
            #print 'Hand', first_hand.id, 'opened:', self.scale_opening_hands[0].is_done()
            #print 'Hand', second_hand.id, 'opened:', self.scale_opening_hands[1].is_done()
            if any(oh.is_done() for oh in self.scale_opening_hands):
                self.stop_scaling()
            else:
                self.continue_scaling(first_hand, second_hand)

    def start_scaling(self, first_hand, second_hand):
        print 'start_scaling'
        self.is_scaling = True

    def stop_scaling(self):
        print 'stop_scaling'
        self.is_scaling = False

    def continue_scaling(self, first_hand, second_hand):
        print 'continue_scaling'

    def reset_scale(self):
        self.scale_closing_hands[0].reset()
        self.scale_closing_hands[1].reset()
        self.scale_opening_hands[0].reset()
        self.scale_opening_hands[1].reset()
        if self.is_scaling:
            self.stop_scaling()

    # grab interface

    def try_grab(self, frame):
        hand = frame.hands[0]
        self.opening_hand.frame(hand)
        self.closing_hand.frame(hand)

        if not self.is_grabbing and self.closing_hand.is_done():
            self.grab(hand)
        if self.is_grabbing and self.opening_hand.is_done():
            self.ungrab()
        if self.is_grabbing:
            self.continue_grab(hand)

    def grab(self, hand):
        print 'GRAB'
        self.is_grabbing = True

        # move origin
        pos = hand.stabilized_palm_position
        self.loc_x_origin = pos.x
        self.loc_y_origin = pos.y
        self.loc_z_origin = pos.z
        send_command('object_move_origin', {})

        # rotate origin
        self.rot_x_origin = hand.direction.pitch
        self.rot_y_origin = hand.direction.yaw
        self.rot_z_origin = hand.direction.roll
        send_command('object_rotate_origin', {})

    def ungrab(self):
        print 'UNGRAB'
        self.is_grabbing = False
        self.loc_x_hand.empty()
        self.loc_y_hand.empty()
        self.loc_z_hand.empty()
        self.rot_x_hand.empty()
        self.rot_y_hand.empty()
        self.rot_z_hand.empty()

        send_command('object_move_end', {})
        send_command('object_rotate_end', {})

    def continue_grab(self, hand):
        pos = hand.stabilized_palm_position
        self.loc_x_hand.add_value(pos.x)
        self.loc_y_hand.add_value(pos.y)
        self.loc_z_hand.add_value(pos.z)

        self.rot_x_hand.add_value(hand.direction.pitch)
        self.rot_y_hand.add_value(hand.direction.yaw)
        self.rot_z_hand.add_value(hand.direction.roll)

        # send motion
        dx = self.loc_x_hand.value - self.loc_x_origin
        dy = self.loc_y_hand.value - self.loc_y_origin
        dz = self.loc_z_hand.value - self.loc_z_origin
        send_command('object_move', { 'loc_x': dx, 'loc_y': dy, 'loc_z': dz})

        # send rotation
        rx = self.rot_x_hand.value - self.rot_x_origin
        ry = self.rot_y_hand.value - self.rot_y_origin
        rz = self.rot_z_hand.value - self.rot_z_origin
        send_command('object_rotate', { 'rot_x': rx, 'rot_y': ry, 'rot_z': rz})

    def reset_grab(self):
        self.opening_hand.reset()
        self.closing_hand.reset()
        if self.is_grabbing:
            self.ungrab()

# leap and its listener/controller
_leap_controller = Leap.Controller()
_current_controller = None

def disable_current_controller():
    global _current_controller
    if _current_controller is None:
        return
    _leap_controller.remove_listener(_current_controller)
    _current_controller = None

defined_controllers = {}

def set_current_controller(ctrl):
    if isinstance(ctrl, (str, unicode)):
        if ctrl not in defined_controllers:
            raise ValueError('Undefined controller %s' % ctrl)
        ctrl = defined_controllers[ctrl]
    disable_current_controller()

    # add listener to leap controller
    global _current_controller
    _current_controller = ctrl()
    _leap_controller.add_listener(_current_controller)
