def spirale(
        taille_spirale: float,
        pas: float
    ) -> list[tuple[float, float]]:
    """Crée une spirale"""
    x = 0
    y = 0
    n_coins_completed = 0
    dist = 1
    l = [(0, 0)]
    while True:
        x += pas * dist
        if x >= taille_spirale/2:
            x = taille_spirale/2
            n_coins_completed += 1
        l.append((x, y))
        if n_coins_completed == 5:
            break
        y += pas * dist
        if y >= taille_spirale/2:
            y = taille_spirale/2
            n_coins_completed += 1
        l.append((x, y))
        dist += 1
        x -= pas * dist
        if x <= -taille_spirale/2:
            x = -taille_spirale/2
            n_coins_completed += 1
        l.append((x, y))
        y -= pas * dist
        if y <= -taille_spirale/2:
            y = -taille_spirale/2
            n_coins_completed += 1
        l.append((x, y))
        dist += 1
    l.append((0, 0))
    return l
