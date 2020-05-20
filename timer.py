#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import logging
import sys
import threading
import time

# Adding this from other file
#

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(10,GPIO.OUT)
my_pwm=GPIO.PWM(10,100)

my_pwm.start(100)
# done Adding from other file

from gpiozero import AngularServo
import dateutil.parser

from agt import AlexaGadget

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

GPIO_PIN = 25

SERVO = AngularServo(GPIO_PIN, initial_angle=90, min_pulse_width=0.0005, max_pulse_width=0.002)

class TimerGadget(AlexaGadget):
    """
    An Alexa Gadget that reacts to a single timer set on an Echo device.
    A servo rotates a disc to indicate the remaining duration of the timer,
    when the timer expires, and when a timer is canceled.
    Threading is used to prevent blocking the main thread when the timer is
    counting down.
    """

    def __init__(self):
        super().__init__()
        self.timer_thread = None
        self.timer_token = None
        self.timer_end_time = None

    def on_alerts_setalert(self, directive):
        """
        Handles Alerts.SetAlert directive sent from Echo Device
        """
        # check that this is a timer. if it is something else (alarm, reminder), just ignore
        if directive.payload.type != 'TIMER':
            logger.info("Received SetAlert directive but type != TIMER. Ignorning")
            return

        # parse the scheduledTime in the directive. if is already expired, ignore
        t = dateutil.parser.parse(directive.payload.scheduledTime).timestamp()
        if t <= 0:
            logger.info("Received SetAlert directive but scheduledTime has already passed. Ignoring")
            return

        # check if this is an update to an alrady running timer (e.g. users asks alexa to add 30s)
        # if it is, just adjust the end time
        if self.timer_token == directive.payload.token:
            logger.info("Received SetAlert directive to update to currently running timer. Adjusting")
            self.timer_end_time = t
            return

        # check if another timer is already running. if it is, just ignore this one
        if self.timer_thread is not None and self.timer_thread.isAlive():
            logger.info("Received SetAlert directive but another timer is already running. Ignoring")
            return

        # start a thread to rotate the servo
        logger.info("Received SetAlert directive. Starting a timer. " + str(int(t - time.time())) + " seconds left..")
        self.timer_end_time = t
        self.timer_token = directive.payload.token

        # run timer in it's own thread to prevent blocking future directives during count down
        self.timer_thread = threading.Thread(target=self._run_timer)
        self.timer_thread.start()

    def on_alerts_deletealert(self, directive):
        """
        Handles Alerts.DeleteAlert directive sent from Echo Device
        """
        # check if this is for the currently running timer. if not, just ignore
        if self.timer_token != directive.payload.token:
            logger.info("Received DeleteAlert directive but not for the currently active timer. Ignoring")
            return

        # delete the timer, and stop the currently running timer thread
        logger.info("Received DeleteAlert directive. Cancelling the timer")
        self.timer_token = None

    def _run_timer(self):
        """
        Runs a timer
        """
        # check every 200ms if we should rotate the servo
        cur_angle = 180
        #adding my_pwm
        my_pwm.start(cur_angle/180)
        start_time = time.time()
        time_remaining = self.timer_end_time - start_time
        self._set_servo_to_angle(cur_angle, timeout=1)
        while self.timer_token and time_remaining > 0:
            time_total = self.timer_end_time - start_time
            time_remaining = max(0, self.timer_end_time - time.time())
            #Adding time_pi =  this should give the correct amount for the pwm but need to convert the time from seconds to minutes
            if time_remaining > 60:          
                time_pi = math.log((time_remaining/60),2)/8-1
            else
                time_pi = (time_remaining/60/8)
            logger.debug('Setting timepi to: ' + str(time_pi))
            next_angle = int(180 * time_remaining / time_total)
            if cur_angle != next_angle:
                self._set_servo_to_angle(cur_angle, timeout=0.3)
                #adding my_pwm
                my_pwm.start(time_pi*100)
                cur_angle = next_angle
            time.sleep(0.2)

        # the timer is expired now, rotate servo back and forth
        # until timer is cancelled
        while self.timer_token:
            self._set_servo_to_angle(175, timeout=1)
            my_pwm.start(100)
            self._set_servo_to_angle(5, timeout=1)
            my_pwm.start(0)
            

        # the timer was cancelled, reset the servo back to initial state
        self._set_servo_to_angle(0, timeout=1)
        my_pwm.start(0)

    def _set_servo_to_angle(self, angle_in_degrees, timeout):
        """
        Sets the servo to the specified angle. Keep this between 0 and 180
        """
        # set the angle of the Servo (min = -90, max = 90)
        SERVO.angle = 90 - float(angle_in_degrees)
        logger.debug('Setting servo to: ' + str(angle_in_degrees))
        time.sleep(timeout)
        SERVO.detach()


if __name__ == '__main__':
    try:
        TimerGadget().main()
    finally:
        logger.debug('Cleaning up GPIO')
        SERVO.close()