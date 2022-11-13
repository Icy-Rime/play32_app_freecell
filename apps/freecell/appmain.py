import hal_screen, hal_keypad
from play32sys import app, path
from ui.select import select_list
from ui.dialog import dialog
from ui.input_text import input_text
import game

def main(app_name, *args, **kws):
    hal_screen.init()
    hal_keypad.init()
    app_path = path.get_app_path(app_name)
    game.init(app_path)
    game.new_game()
    main_loop(app_name)
    # game.game_loop()
    # app.reset_and_run_app("")
    
def main_loop(app_name):
    data_path = path.get_data_path(app_name)
    if not path.exist(data_path):
        path.mkdirs(data_path)
    while True:
        win = game.game_loop()
        if win:
            dialog("Congratulation!", "You Win")
            sel = select_list("Menu", [
                "New Game",
                "Quit",
            ])
            if sel == 0:
                game.new_game()
                continue
            elif sel == 1:
                app.reset_and_run_app("")
        sel = select_list("Menu", [
            "Undo",
            "Save",
            "Load",
            "New Game",
            "Select Game",
            "Quit",
        ])
        if sel == 0:
            game.fc.undo()
        elif sel == 1:
            slot = select_list("Save Slot", [ str(i + 1) for i in range (10) ])
            if slot >= 0:
                name = str(slot + 1) + ".sav"
                try:
                    with open(path.join(data_path, name), "wb") as f:
                        game.fc.save(f)
                except:
                    dialog("Save Failed.", "Result")
        elif sel == 2:
            slot = select_list("Load Slot", [ str(i + 1) for i in range (10) ])
            if slot >= 0:
                name = str(slot + 1) + ".sav"
                try:
                    with open(path.join(data_path, name), "rb") as f:
                        game.fc.load(f)
                except:
                    dialog("Load Failed.", "Result")
        elif sel == 3:
            game.new_game()
        elif sel == 4:
            seed = input_text("", "Seed")
            if seed:
                try:
                    game.new_game(int(seed))
                except:
                    dialog("Bad Seed.", "Result")
        elif sel == 5:
            app.reset_and_run_app("")