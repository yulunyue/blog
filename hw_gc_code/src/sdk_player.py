from typing import List
DIRCTION = [[0, 1], [1, 0], [0, -1], [-1, 0]]
MOVE_NAMES = ['RIGHT', 'DOWN', 'LEFT', 'UP']
CAMERE_SHAPE = [
    [[0, -1], [0, 0], [0, 1]],
    [[-1, 0], [0, 0], [1, 0]],
    [[-1, 0], [0, 0], [0, 1]],
    [[1, 0], [0, 0], [0, 1]],
    [[1, 0], [0, 0], [0, -1]],
    [[-1, 0], [0, 0], [0, -1]],
    [[0, -2], [0, -1], [0, 0], [0, 1], [0, 2]],
    [[-2, 0], [-1, 0], [0, 0], [1, 0], [2, 0]],
    [[-1, 0], [1, 0], [0, 0], [0, 1], [0, -1]],
    [[-1, -1], [-1, 1], [0, 0], [1, 1], [1, -1]]
]


class Cell:
    def __init__(self, x, y, data='*') -> None:
        self.x = x
        self.y = y
        self.is_obstacle = False  # 标识该单元格是否是障碍
        self.land_score = 0  # 单元格摄像头分数
        self.energy = 0  # 机器人移动到该单元格能获取到能量
        self.robot_id = None
        self.owner = -1
        self.warranty_period = 0  # 单元格保护回合数
        self.set_data(data)

    def set_data(self, data):
        if data == '#':
            self.is_obstacle = True
        elif ord(data) >= ord('0') and ord(data) <= ord('9'):
            self.land_score = ord(data) - ord('0')
        elif ord(data) >= ord('a') and ord(data) <= ord('z'):
            self.energy = ord(data) - ord('a')+3
        elif ord(data) >= ord('A') and ord(data) <= ord('Z'):
            self.robot_id = ord(data) - ord('A')

    def set_energy(self, energy):
        if self.energy != 0:
            return
        if self.robot_id is not None:
            return
        if self.is_obstacle:
            return
        self.energy = energy


class Player:
    c_name = "sdk"

    def prepare(self, player_id, energies_limit,
                camera_unit_energy, obstacles, land_scores,
                max_round=500, warranty_period=20,
                robot_num=4, **kwargs
                ) -> None:
        self.warranty_period = warranty_period
        self.world_height = len(land_scores)
        self.world_width = len(land_scores[0])
        self.max_round = max_round
        self.max_player_round = max_round/2
        self.worlds: List[List[Cell]] = [[Cell(j, i) for j in range(self.world_width)]
                                         for i in range(self.world_height)]
        self.player_id = player_id
        self.energies_limit = energies_limit
        self.camera_unit_energy = camera_unit_energy
        for o in obstacles:
            self.cell(o['y'], o['x']).is_obstacle = True
        for i in range(len(land_scores)):
            for j in range(len(land_scores[i])):
                if land_scores[i][j]:
                    self.cell(i, j).land_score = land_scores[i][j]
        self.visite_ways = dict()
        self.cameras_cell: List[Cell] = []
        self.robot_num = robot_num

    def log(self):
        pass

    def cell(self, y, x) -> Cell:
        return self.worlds[y][x]

    def action(self, round, scores, energies, accumulated_energies, robots, occupied_lands):
        self.robots: List = []
        self.others_robots: List = []
        self.current_round = round
        self.scores = scores[:]
        self.accumulated_energies = accumulated_energies[:]
        for o in occupied_lands:
            c = self.cell(o['y'], o['x'])
            c.warranty_period = o["warranty_period"]
            c.owner = o["owner"]
        for robot in robots:
            r = dict(
                player_id=robot["player_id"], robot_id=robot["robot_id"],
                y=robot["y"], x=robot["x"], move="NOP", install_camera=None
            )
            if r['player_id'] == self.player_id:
                self.robots.append(r)
            else:
                self.others_robots.append(r)
            self.cell(r['y'], r['x']).robot_id = r["robot_id"]
        self.all_robots = self.robots + self.others_robots
        for engine in energies:
            self.cell(engine['y'], engine['x']).energy = engine['amount']
        for r in self.robots:
            self.bfs(r)
        return dict(actions=[
            dict(robot_id=r["robot_id"], move=r["move"],
                 install_camera=r["install_camera"])
            for r in self.robots
        ])

    def get_camera_max_score(self, c1: Cell):
        cam_index = None
        max_cam = 0
        cost_max = 0
        for i, yx in enumerate(CAMERE_SHAPE):
            cost = len(CAMERE_SHAPE[i])*self.camera_unit_energy
            if self.accumulated_energies[self.player_id] < cost:
                continue
            cam_score = 0
            for iy, ix in yx:
                y, x = c1.y+iy, c1.x+ix
                if y < 0 or y >= len(self.worlds) or x < 0 or x >= len(self.worlds[0]):
                    # print("gg")
                    cam_score = 0
                    break
                c = self.cell(y, x)
                if c.owner == -1:
                    cam_score += c.land_score
                elif c.owner == self.player_id:
                    pass
                else:
                    if c.warranty_period <= 0:
                        cam_score += 2*c.land_score
            if cam_score > max_cam:
                max_cam = cam_score
                cam_index = i
                cost_max = cost
                # print(c1.y, c1.x, max_cam, cam_index)
        self.accumulated_energies[self.player_id] -= cost_max
        return cam_index

    def bfs(self, r):
        visite_list = [[r["y"], r["x"], 0]]
        visite_map = {
            (r["y"], r["x"]): []
        }
        while len(visite_list):
            y, x, l = visite_list.pop(0)
            c = self.worlds[y][x]
            camera = self.get_camera_max_score(c)
            if camera is not None:
                if l == 0:
                    r["install_camera"] = camera
                else:
                    r["move"] = visite_map[(y, x)][0]
                return
            if c.energy:
                c.energy = 0
                r["move"] = visite_map[(y, x)][0]
                return
            for i, yx in enumerate(DIRCTION):
                next_y, next_x = y+yx[0], x+yx[1]
                if next_y < 0 or next_y >= len(self.worlds)-1 or next_x < 0 or next_x >= len(self.worlds[0])-1:
                    continue
                if self.cell(next_y, next_x).is_obstacle:
                    continue
                if self.cell(next_y, next_x).robot_id is not None:
                    continue
                if (next_y, next_x) in visite_map:
                    continue
                visite_map[(next_y, next_x)] = visite_map[(y, x)] + \
                    [MOVE_NAMES[i]]
                visite_list.append([next_y, next_x, l+1])
