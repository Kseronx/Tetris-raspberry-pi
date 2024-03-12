import random
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.led_matrix.device import max7219
import RPi.GPIO as GPIO
from PIL import Image
from time import time
from time import sleep
from RPLCD.i2c import CharLCD

# Ustawienia gry
ROWS = 32
COLS = 8  # Zmiana szerokości planszy na 32
high_score_file = "highscore.txt"

# Kształty bloków Tetrisa
SHAPES = [
    [[1, 1, 1, 1]],
    [[1, 1], [1, 1]],
    [[1, 1, 1], [0, 1, 0]],
    [[1, 1, 1], [1, 0, 0]],
    [[1, 1, 1], [0, 0, 1]],
    [[1, 1, 0], [0, 1, 1]],
    [[0, 1, 1], [1, 1, 0]],
]

# GPIO Piny dla przycisków
LEFT_PIN = 26
RIGHT_PIN = 20
DOWN_PIN = 19
ROTATE_PIN = 16
RESET_PIN = 12


# Inicjalizacja GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(DOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ROTATE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RESET_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Konfiguracja wyświetlacza LED
serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=3)

img = Image.new("1", (COLS, ROWS), "black")
pixelMap = img.load()


class Delays:
    button = dict()
    def __init__(self):
        self.button[LEFT_PIN] = time()
        self.button[RIGHT_PIN] = time()
        self.button[DOWN_PIN] = time()
        self.button[ROTATE_PIN] = time()

        self.last = time()

class LCD:
    def draw_score(self, score, high_score):
        self.lcd.clear()
        self.lcd.write_string('SCORE: {}\n\rBEST: {}'.format(score, high_score))

    def draw_game_over(self, score):
        self.lcd.clear()
        self.lcd.write_string("SCORE: {}\n\r   GAME OVER!   ".format(score))

    def __init__(self,high_score):
        self.lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8)
        self.draw_score(0,high_score)


class Tetris:
    def __init__(self):
        self.isPlaying = True
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.current_block = self.spawn_block()
        self.score = 0
        self.interval = 0.5

        self.high_score = self.load_score_file()
        self.lcd = LCD(self.high_score)


    def load_score_file(self):
        file = open(high_score_file, "r")
        score = file.read()
        score = 0 if (score == "") else int(score)
        file.close()
        return score

    def reset(self):
        self.isPlaying = True
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.current_block = self.spawn_block()
        self.score = 0
        self.interval = 0.5

        self.lcd = LCD(self.high_score)


    def check_game_over(self):
        if self.board[0][3] == 1:
            self.isPlaying = False

            if(self.score > self.high_score):
                self.high_score = self.score
                file = open(high_score_file, "w")
                file.write(str(self.score))
                file.close()
            self.lcd.draw_game_over(self.score)



    def spawn_block(self):
        shape = random.choice(SHAPES)
        color = 1  # Kolor bloku (1 to indeks koloru na wyświetlaczu LED)
        block = {
            'shape': shape,
            'color': color,
            'row': 0,
            'col': (COLS - len(shape[0])) // 2,
        }

        self.check_game_over()

        return block

    def check_collision(self):
        for i, row in enumerate(self.current_block['shape']):
            for j, cell in enumerate(row):
                if cell and (self.current_block['row'] + i >= ROWS or
                             self.current_block['col'] + j < 0 or
                             self.current_block['col'] + j >= COLS or
                             self.board[self.current_block['row'] + i][self.current_block['col'] + j]):
                    return True
        return False

    def merge_block(self):
        for i, row in enumerate(self.current_block['shape']):
            for j, cell in enumerate(row):
                if cell:
                    self.board[self.current_block['row'] + i][self.current_block['col'] + j] = self.current_block[
                        'color']

    def clear_lines(self):
        lines_to_clear = [i for i, row in enumerate(self.board) if all(row)]
        for line in lines_to_clear:
            del self.board[line]
            self.board.insert(0, [0] * COLS)
        if(lines_to_clear):
            self.score += (len(lines_to_clear)**2)*100
            self.lcd.draw_score(self.score,self.high_score)
            tetris.interval *= 0.95

    def move_block(self, direction):
        if direction == LEFT_PIN:
            self.current_block['col'] -= 1
            if self.check_collision():
                self.current_block['col'] += 1
        elif direction == RIGHT_PIN:
            self.current_block['col'] += 1
            if self.check_collision():
                self.current_block['col'] -= 1
        elif direction == DOWN_PIN:
            self.current_block['row'] += 1
            if self.check_collision():
                self.current_block['row'] -= 1
                self.merge_block()
                self.clear_lines()
                self.current_block = self.spawn_block()
        elif direction == ROTATE_PIN:
            self.rotate_block()

    def rotate_block(self):
        original_shape = self.current_block['shape']
        self.current_block['shape'] = list(zip(*original_shape[::-1]))
        if self.check_collision():
            self.current_block['shape'] = original_shape

    def draw_board(self):
        with canvas(device) as draw:
            for i in range(ROWS):
                for j in range(COLS):
                    #print('X' if self.board[i][j] else ' ',end='')
                    if self.current_block['row'] <= i < self.current_block['row'] + len(self.current_block['shape']) and \
                            self.current_block['col'] <= j < self.current_block['col'] + len(
                        self.current_block['shape'][0]) and \
                            self.current_block['shape'][i - self.current_block['row']][j - self.current_block['col']]:
                        draw.point((j, i), fill="white")
                    elif self.board[i][j]:
                        draw.point((j, i), fill="white")
                #print()



# Przykładowe użycie
tetris = Tetris()
delays = Delays()

def reset():
    tetris.reset()


GPIO.add_event_detect(ROTATE_PIN, GPIO.FALLING, callback=lambda x: tetris.move_block(ROTATE_PIN), bouncetime=200)
GPIO.add_event_detect(RESET_PIN, GPIO.FALLING, callback=lambda x: reset(), bouncetime=1000)

try:
    while True:
        while tetris.isPlaying:
            if GPIO.input(LEFT_PIN) == GPIO.LOW and time() - delays.button[LEFT_PIN] > 0.15:
                delays.button[LEFT_PIN] = time()
                tetris.move_block(LEFT_PIN)
            elif GPIO.input(RIGHT_PIN) == GPIO.LOW and time() - delays.button[RIGHT_PIN] > 0.15:
                delays.button[RIGHT_PIN] = time()
                tetris.move_block(RIGHT_PIN)
            if GPIO.input(DOWN_PIN) == GPIO.LOW and time() - delays.button[DOWN_PIN] > 0.05:
                delays.button[DOWN_PIN] = time()
                tetris.move_block(DOWN_PIN)

            if time() - delays.last > tetris.interval:
                tetris.move_block(DOWN_PIN)
                delays.last = time()
            tetris.draw_board()
        else:
            sleep(1)
except KeyboardInterrupt:
    GPIO.cleanup()
    tetris.lcd.lcd.clear()




