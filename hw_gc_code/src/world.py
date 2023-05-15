from .sdk_player import Player, Cell, CAMERE_SHAPE
from .gold_player1 import Player as Player2
from typing import List
import os
import json
import sys
import random
ACTION_MAP = dict(
    n=[0, 0], NOP=[0, 0],
    u=[-1, 0], UP=[-1, 0],
    d=[1, 0], DOWN=[1, 0],
    l=[0, -1], LEFT=[0, -1],
    r=[0, 1], RIGHT=[0, 1]
)


class World:
    def __init__(self) -> None:
        self.players: List[Player] = [Player(), Player2()]
        self.scores = [0, 0]
        self.accumulated_energies = [0, 0]
        self.worlds: List[List[Cell]] = []
        self.cells: List[Cell] = []
        if len(sys.argv) <= 1:
            self.max_round = 500
        else:
            self.max_round = int(sys.argv[1])
        self.warranty_period = 20
        random.seed(7)

    def load_map(self, camera_unit_energy, world, robot_num: str, energies_limit):
        self.camera_unit_energy = camera_unit_energy
        robot_pos = [int(v) for v in robot_num.split(" ")]
        self.robot_num = len(robot_pos)//4
        self.energies_limit = energies_limit
        for i, row in enumerate(world):
            self.worlds.append([])
            for j, col in enumerate(row.split(" ")):
                self.worlds[-1].append(Cell(j, i, col))
                self.cells.append(self.worlds[-1][-1])

        for i in range(0, len(robot_pos), 2):
            self.worlds[robot_pos[i+1]][robot_pos[i]].robot_id = i//2
        self.robots = sorted(self.get_robots(), key=lambda v: v["robot_id"])

    def land_scores(self):
        return [[col.land_score for col in rows] for rows in self.worlds]

    def obstacles(self):
        return [dict(y=c.y, x=c.x) for c in self.cells if c.is_obstacle]

    def get_robots(self):
        return [dict(
            y=c.y, x=c.x,
            actions=[],
            robot_id=c.robot_id,
            player_id=c.robot_id // self.robot_num
        ) for c in self.cells if c.robot_id is not None]

    def engines(self):
        return [dict(
            y=c.y, x=c.x,
            amount=c.energy,
        ) for c in self.cells if c.energy]

    def occupied_lands(self):
        return [dict(
            y=c.y, x=c.x,
            owner=c.owner,
            warranty_period=c.warranty_period
        ) for c in self.cells if c.owner != -1]

    def run(self):
        for i, p in enumerate(self.players):
            p.prepare(
                i, self.energies_limit, self.camera_unit_energy,
                self.obstacles(),
                self.land_scores(),
                self.max_round, robot_num=self.robot_num
            )
        for i in range(self.max_round):
            p = self.players[i % len(self.players)]
            self.pre()
            actions = p.action(
                i,
                self.scores, self.engines(),
                self.accumulated_energies,
                self.robots,
                self.occupied_lands()
            )
            # print(f"round {p} {i} {actions}")
            self.do_actions(actions)

    def pre(self):
        y, x, flag = random.randint(
            0, len(self.worlds)-1), random.randint(0, len(self.worlds[0])-1), random.random()
        if flag < 0.8:
            self.worlds[y][x].set_energy(random.randint(1, 5))

        for c in self.cells:
            if c.warranty_period > 0:
                c.warranty_period -= 1  # 每回合之前保护回合数减1

    def do_actions(self, actions):
        for action in actions["actions"]:
            info = self.do_action(**action)
            if info:
                raise Exception("do_error", info)

    def put_camera(self, r, install_camera):
        ac_engy = self.accumulated_energies[r["player_id"]]
        cost = len(CAMERE_SHAPE[install_camera])*self.camera_unit_energy
        if ac_engy < cost:
            return f'{ac_engy}<{cost} 放置摄像头{install_camera}能量不足'
        self.accumulated_energies[r["player_id"]] -= cost
        for iy, ix in CAMERE_SHAPE[install_camera]:
            y, x = r["y"]+iy, r["x"]+ix
            if y < 0 or y >= len(self.worlds) or x < 0 or x >= len(self.worlds[0]):
                return f"放置摄像头超出边界:{y}:{x}"
            c: Cell = self.worlds[y][x]
            if c.owner == -1:
                c.owner = r["player_id"]
                self.scores[r["player_id"]] += c.land_score
                c.warranty_period = self.warranty_period
            elif c.owner == r["player_id"]:
                c.warranty_period = self.warranty_period
            else:
                if c.warranty_period == 0:
                    self.scores[c.owner] -= c.land_score
                    c.warranty_period = self.warranty_period
                    c.owner = r["player_id"]
                    self.scores[c.owner] += c.land_score
                    c.warranty_period = self.warranty_period

    def move_to(self, r, iy, ix):
        y, x = r["y"]+iy, r["x"]+ix
        if y < 0 or y >= len(self.worlds) or x < 0 or x >= len(self.worlds[0]):
            return f"机器人移动超出边界:{r} {y},{x}"
        if self.worlds[y][x].is_obstacle:
            return f"机器人碰墙:{r}"
        if self.worlds[y][x].robot_id is not None:
            return f"机器人碰撞机器人:{r}"
        self.accumulated_energies[r["player_id"]] = min(
            self.accumulated_energies[r["player_id"]]+self.worlds[y][x].energy,
            self.energies_limit
        )

        self.worlds[y][x].energy = 0
        self.worlds[r["y"]][r["x"]].robot_id = None
        r["y"], r["x"] = y, x
        self.worlds[y][x].robot_id = r["robot_id"]

    def do_action(self, robot_id, move="NOP", install_camera=None, target=None):
        ret = ""
        r = self.robots[robot_id]

        if install_camera is not None:
            r["actions"].append(str(install_camera))
            ret = self.put_camera(r, install_camera)
        else:
            r["actions"].append(str(move)[0])
            if move == "NOP":
                return ret
            ret = self.move_to(r, *ACTION_MAP[move])

        return ret

    def print(self):
        for r in self.robots:
            print(f'{chr(ord("A")+r["robot_id"])}:{"".join(r["actions"])}')
        print(
            f'energies:{self.accumulated_energies} scores:{self.scores}')
        if self.scores[0] < self.scores[1] and self.players[0].c_name == 'sdk':
            print("失败", self.players[0].c_name)
            exit()
        if self.scores[0] > self.scores[1] and self.players[1].c_name == 'sdk':
            print("失败", self.players[1].c_name)
            exit()

    def run_all(self):
        for name in os.listdir("map"):
            for rd in range(2):
                if rd == 1:
                    self.players.reverse()
                print("run ", name, self.players)
                data = json.load(open(f"map/{name}", "r"))
                self.load_map(**data)
                self.run()
                self.print()
        print("成功")


if __name__ == "__main__":
    wd = World()
    wd.run_all()
