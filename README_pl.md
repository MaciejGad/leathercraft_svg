# laser_svg

Biblioteka do generowania prostych plików SVG dla cięcia laserowego, szycia i kreślenia.
Obsługuje kształty, punkty na krawędziach, dziurki pod szycie oraz eksport do PNG z białym tłem.

Najważniejsze cechy:

- brak CSS w wygenerowanym SVG, style są zapisywane inline na elementach,
- warstwy: `cut`, `stitch`, `crease`, `guide`,
- automatyczne generowanie dziurek na krawędziach figur,
- eksport SVG i PNG,
- proste API oparte o klasy geometryczne.

## Instalacja

Projekt używa Pythona 3.13+ i do eksportu PNG potrzebuje `cairosvg`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install cairosvg
```

Jeśli chcesz tylko generować SVG, sama biblioteka działa też bez dodatkowych pakietów.

## Szybki start

```python
from laser_svg import Rectangle, SvgDocument

doc = SvgDocument(width_mm=100, height_mm=60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0)

doc.save("example.svg")
doc.save_png("example.png", background_color="white")
```

## Uruchomienie przykładu

W repozytorium jest gotowy przykład:

```bash
./.venv/bin/python example_shapes.py
```

To wygeneruje:

- `example_shapes.svg`
- `example_shapes.png`

Skrypt `test.sh` uruchamia ten sam przykład i otwiera PNG.

## Format SVG

Wygenerowany SVG:

- nie korzysta z CSS,
- zapisuje kolory, grubość linii i kreskowanie bezpośrednio na elementach,
- używa `viewBox` zgodnego z rozmiarem dokumentu w milimetrach,
- stosuje `vector-effect="non-scaling-stroke"`.

To zwiększa kompatybilność z rendererami, które słabo obsługują style klasowe.

## Warstwy i style

Domyślne warstwy są zdefiniowane jako:

- `cut` - warstwa cięcia, kolor czerwony, `#ff0000`, grubość `0.1`
- `stitch` - warstwa szycia, kolor niebieski, `#0000ff`, grubość `0.1`
- `crease` - warstwa bigowania / zgięcia, kolor zielony, `#00aa00`, grubość `0.1`, kreskowanie `3 2`
- `guide` - warstwa pomocnicza / prowadząca, kolor szary, `#777777`, grubość `0.1`, kreskowanie `2 2`

Każdy element dodany do dokumentu może być przypisany do jednej z tych warstw.

## API

### `SvgDocument(width_mm, height_mm, styles=None)`

Tworzy dokument SVG.

Parametry:

- `width_mm` - szerokość dokumentu w milimetrach,
- `height_mm` - wysokość dokumentu w milimetrach,
- `styles` - opcjonalny słownik stylów typu `dict[str, StrokeStyle]`.

Jeśli nie podasz `styles`, zostaną użyte style domyślne.

### `doc.add_shape(shape, layer="cut")`

Dodaje kształt jako ścieżkę SVG.

Parametry:

- `shape` - obiekt dziedziczący po `Shape`,
- `layer` - warstwa docelowa: `cut`, `stitch`, `crease` lub `guide`.

### `doc.add_path(d, layer="cut")`

Dodaje surową ścieżkę SVG.

Parametry:

- `d` - atrybut `d` ścieżki SVG,
- `layer` - warstwa stylu.

### `doc.add_line(x1, y1, x2, y2, layer="cut")`

Dodaje linię SVG.

Parametry:

- `x1`, `y1` - punkt startowy,
- `x2`, `y2` - punkt końcowy,
- `layer` - warstwa stylu.

### `doc.add_circle(x, y, radius, layer="cut")`

Dodaje okrąg SVG.

Parametry:

- `x`, `y` - środek,
- `radius` - promień,
- `layer` - warstwa stylu.

### `doc.add_holes(shape, edges="all", spacing=5.0, hole_radius=1.2, inset=4.0, layer="cut", include_corners=False)`

Dodaje dziurki wyliczone na podstawie krawędzi figury.

Parametry:

- `shape` - figura, która implementuje `hole_points()`,
- `edges` - które krawędzie użyć: `"all"` albo lista indeksów,
- `spacing` - odstęp między dziurkami,
- `hole_radius` - promień dziurek,
- `inset` - odsunięcie od krawędzi,
- `layer` - warstwa dziurek,
- `include_corners` - jeśli `True`, punktowanie zaczyna się od narożników; jeśli `False`, dziurki są odsunięte od końców krawędzi.

### `doc.add_stitch_holes(...)`

Alias dla `add_holes(...)` z tymi samymi parametrami.

### `doc.save(path)`

Zapisuje SVG do pliku.

### `doc.save_png(path, background_color="white")`

Zapisuje PNG przez CairoSVG.

Parametry:

- `path` - ścieżka do pliku PNG,
- `background_color` - kolor tła, domyślnie `white`.

## Klasy geometryczne

### `Point(x, y)`

Punkt 2D.

Pola:

- `x`
- `y`

### `Rectangle(x, y, width, height)`

Prostokąt osiowo wyrównany.

Parametry:

- `x`, `y` - lewy górny róg,
- `width` - szerokość,
- `height` - wysokość.

Metoda:

- `path_d()` - zwraca ścieżkę SVG,
- `hole_points(edges="all", spacing=5.0, inset=4.0, include_corners=False)` - zwraca punkty dziurek na wskazanych krawędziach.

Indeksy krawędzi prostokąta:

- `0` - góra,
- `1` - prawa,
- `2` - dół,
- `3` - lewa.

### `RoundedRectangle(x, y, width, height, radius=5.0)`

Prostokąt z zaokrąglonymi narożnikami.

Parametry:

- `x`, `y`, `width`, `height` - jak wyżej,
- `radius` - promień zaokrąglenia.

### `Circle(cx, cy, radius)`

Okrąg.

Parametry:

- `cx`, `cy` - środek,
- `radius` - promień.

Metoda `hole_points(...)` dla okręgu rozmieszcza punkty wokół okręgu pomocniczego o promieniu `radius - inset`.

### `Triangle(p1, p2, p3)`

Trójkąt z trzema punktami.

Parametry:

- `p1`, `p2`, `p3` - wierzchołki jako `Point`.

#### `Triangle.from_box(x, y, width, height)`

Tworzy trójkąt wpisany w prostokąt.

Punkty:

- `p1` - środek górnej krawędzi,
- `p2` - prawy dolny róg,
- `p3` - lewy dolny róg.

Indeksy krawędzi trójkąta:

- `0` - `p1 -> p2`,
- `1` - `p2 -> p3`,
- `2` - `p3 -> p1`.

### `RoundedTriangle(p1, p2, p3, radius=5.0)`

Trójkąt z zaokrąglonymi narożnikami.

Parametry:

- `p1`, `p2`, `p3` - wierzchołki,
- `radius` - promień zaokrąglenia narożników.

## Parametry wspólne dla `hole_points(...)`

Wszystkie figury implementują metodę:

```python
hole_points(
    edges="all",
    spacing=5.0,
    inset=4.0,
    include_corners=False,
)
```

Znaczenie parametrów:

- `edges` - krawędzie, na których mają pojawić się punkty,
- `spacing` - odstęp między kolejnymi punktami,
- `inset` - odsunięcie punktów od krawędzi lub narożników,
- `include_corners` - czy uwzględniać narożniki jako punkty startowe i końcowe.

Jeśli `edges="all"`, używane są wszystkie krawędzie figury.

## Przykłady

### Prostokąt z dziurkami na wszystkich krawędziach

```python
from laser_svg import Rectangle, SvgDocument

doc = SvgDocument(100, 60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, edges="all", spacing=8.0, hole_radius=1.2, inset=5.0)
doc.save("rect.svg")
```

### Trójkąt z dziurkami tylko na wybranych krawędziach

```python
from laser_svg import Point, Triangle, SvgDocument

doc = SvgDocument(120, 90)
shape = Triangle(Point(20, 20), Point(100, 70), Point(20, 70))

doc.add_shape(shape)
doc.add_holes(shape, edges=[0, 2], spacing=10.0, hole_radius=1.0, inset=6.0)
doc.save("triangle.svg")
```

### Eksport PNG z białym tłem

```python
doc.save_png("output.png", background_color="white")
```

## Kompatybilność

Zachowanie projektu zostało zoptymalizowane pod renderery, które gorzej obsługują CSS w SVG.
Jeśli używasz zewnętrznego narzędzia do rasteryzacji, preferuj narzędzia z dobrą obsługą SVG inline, np. CairoSVG lub Inkscape.

## Struktura plików

- `laser_svg.py` - biblioteka i modele geometryczne,
- `example_shapes.py` - przykład generujący kilka figur,
- `test.sh` - prosty skrypt uruchamiający przykład,
- `README.md` - dokumentacja.

## Uwagi praktyczne

- Jeśli chcesz zmienić wygląd elementów, najprościej podać własny słownik `styles` do `SvgDocument`.
- Jeśli chcesz odległości innych niż domyślne, reguluj `spacing` i `inset`.
- Jeśli chcesz gęstsze lub większe dziurki, zmieniaj `hole_radius`.
