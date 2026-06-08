# leathercraft_svg

![Logo leathercraft_svg](logo-720.png)

Biblioteka do generowania prostych plików SVG dla cięcia laserowego, szycia i kreślenia.
Obsługuje kształty, punkty na krawędziach, dziurki pod szycie oraz eksport do PNG z białym tłem.

Najważniejsze cechy:

- brak CSS w wygenerowanym SVG, style są zapisywane inline na elementach,
- warstwy: `cut`, `stitch`, `crease`, `guide`,
- automatyczne generowanie dziurek na krawędziach figur,
- opcjonalny laserowy wzór ściegu (krótkie odcinki linii) zamiast dziurek,
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
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(width_mm=100, height_mm=60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0)

doc.save("example.svg")
doc.save_png("example.png", background_color="white")
```

## Uruchomienie przykładów

Jest też mniejszy, bardziej konkretny przykład w `sample.py`:

```bash
./.venv/bin/python sample.py
```

To wygeneruje:

- `sample.svg`
- `sample.png`

Przykład `sample.py` pokazuje `RoundedRectangle` z wzorem ściegu pod kątem 45 stopni na prawej, dolnej i lewej krawędzi:

```python
from leathercraft_svg import RoundedRectangle, SvgDocument


doc = SvgDocument(width_mm=140, height_mm=90)
shape = RoundedRectangle(20, 15, 100, 60, radius=10)

doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    edges=[1, 2, 3],
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=45.0,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.8,
)

doc.save("sample.svg")
doc.save_png("sample.png", background_color="white")
```

Ilustracja:

![Rounded rectangle with 45 degree stitches on the right, bottom, and left edges](sample.png)

Jest też szerszy przykład-galeria w `all_shapes.py`:

```bash
./.venv/bin/python all_shapes.py
```

To wygeneruje:

- `all_shapes.svg`
- `all_shapes.png`

Skrypt `all_shapes.py` generuje poglądowy zestaw obsługiwanych wariantów figur oraz układów ściegów i dziurek.

Ilustracja:

![Overview of all generated shapes](all_shapes.png)

Pełny przegląd testów wizualnych z fragmentami kodu i obrazami bazowymi znajdziesz w [VISUAL_TESTS.md](VISUAL_TESTS.md).

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

### `doc.add_stitch_pattern(shape, edges="all", spacing=5.0, stitch_length=2.0, inset=4.0, layer="stitch", include_corners=False, stitch_thickness=None, stitch_angle_deg=0.0)`

Dodaje laserowy wzór ściegu (krótkie odcinki linii) na wybranych krawędziach figury.

Parametry:

- `shape` - figura implementująca `stitch_segments()`,
- `edges` - które krawędzie użyć: `"all"` albo lista indeksów,
- `spacing` - odstęp między ściegami,
- `stitch_length` - długość pojedynczego odcinka ściegu,
- `inset` - odsunięcie od krawędzi,
- `layer` - warstwa ściegów,
- `include_corners` - czy dodawać ściegi także w narożnikach,
- `stitch_thickness` - opcjonalna grubość linii dla ściegów (jeśli `None`, używana jest domyślna grubość warstwy).
- `stitch_angle_deg` - kąt pochylenia ściegu w stopniach (domyślnie `0.0` = na płasko, można podać własną wartość, np. `45`).

### `doc.add_stitch_on_polyline(points, spacing=5.0, stitch_length=2.0, stitch_angle_deg=0.0, layer="stitch", stitch_thickness=None)`

Dodaje znaczniki ściegu rozmieszczone wzdłuż otwartej polilinii.

Parametry:

- `points` - lista krotek `(x, y)`,
- `spacing` - odstęp między środkami ściegów,
- `stitch_length` - długość każdego ściegu,
- `stitch_angle_deg` - pochylenie względem kierunku ścieżki,
- `layer` - warstwa stylu,
- `stitch_thickness` - opcjonalne nadpisanie grubości linii.

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

### `Polygon(points, smooth=False)`

Figura zdefiniowana przez jawną listę krotek `(x, y)`.

Parametry:

- `points` - uporządkowana lista krotek `(x, y)` tworzących zamknięty wielokąt,
- `smooth` - jeśli `True`, kontur jest rysowany krzywymi Béziera zamiast odcinków prostych.

Metody `hole_points(...)` i `stitch_segments(...)` automatycznie przesuwają granicę wielokąta do wewnątrz o wartość `inset`.

#### `Polygon.from_mirror(half_points, center_x, smooth=False)`

Tworzy symetryczny zamknięty wielokąt z jednej połowy konturu.

`half_points` powinno zaczynać i kończyć się na osi symetrii (`x == center_x`). Odbita prawa połowa jest dołączana w odwrotnej kolejności, tworząc jeden ciągły zamknięty kontur.

```python
from leathercraft_svg import Polygon, SvgDocument

doc = SvgDocument(150, 80)

lewa_polowa = [
    (75, 5),
    (40, 5),
    (20, 40),
    (40, 75),
    (75, 75),
]

shape = Polygon.from_mirror(lewa_polowa, center_x=75, smooth=True)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
doc.save("polygon.svg")
```

### `offset_polyline(points, distance, side="right", miter_limit=8.0)`

Przesuwa otwartą polilinię o `distance` mm.

Parametry:

- `points` - lista krotek `(x, y)`,
- `distance` - odległość przesunięcia w mm,
- `side` - `"right"` lub `"left"` względem kierunku ruchu wzdłuż ścieżki,
- `miter_limit` - narożniki ostrzejsze niż `distance × miter_limit` są ścięte.

Zwraca nową `list[tuple[float, float]]`.

### `mirror_polyline(points, center_x)`

Odbija poziomo listę krotek `(x, y)` względem `center_x`.

Przydatne do generowania prawej ścieżki ściegu z lewej.

### `stitch_segments_on_open_polyline(points, spacing, stitch_length, stitch_angle_deg=0.0)`

Zwraca segmenty ściegu (`list[tuple[Point, Point]]`) rozmieszczone co `spacing` mm wzdłuż otwartej polilinii. Pierwszy ścieg jest umieszczony w odległości `spacing` od początku ścieżki.

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
from leathercraft_svg import Rectangle, SvgDocument

doc = SvgDocument(100, 60)
shape = Rectangle(10, 10, 80, 40)

doc.add_shape(shape)
doc.add_holes(shape, edges="all", spacing=8.0, hole_radius=1.2, inset=5.0)
doc.save("rect.svg")
```

### Trójkąt z dziurkami tylko na wybranych krawędziach

```python
from leathercraft_svg import Point, Triangle, SvgDocument

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

### Symetryczny wielokąt z dziurkami pod szycie

```python
from leathercraft_svg import Polygon, SvgDocument

doc = SvgDocument(150, 80)

lewa_polowa = [
    (75, 5),
    (40, 5),
    (20, 40),
    (40, 75),
    (75, 75),
]

shape = Polygon.from_mirror(lewa_polowa, center_x=75, smooth=True)
doc.add_shape(shape, layer="cut")
doc.add_holes(shape, spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
doc.save("polygon.svg")
```

### Otwarta polilinia z przesuniętym szwem ściegów

```python
from leathercraft_svg import SvgDocument, StrokeStyle, offset_polyline, mirror_polyline

doc = SvgDocument(150, 100, styles={
    "cut":    StrokeStyle("#ff0000", 0.12),
    "stitch": StrokeStyle("#0000ff", 0.35),
})

lewa_krawedz = [(30, 10), (20, 50), (30, 90)]
lewy_szew  = offset_polyline(lewa_krawedz, distance=4.0, side="right")
prawy_szew = mirror_polyline(lewy_szew, center_x=75)

doc.add_stitch_on_polyline(lewy_szew,  spacing=6, stitch_length=2.4, layer="stitch")
doc.add_stitch_on_polyline(prawy_szew, spacing=6, stitch_length=2.4, layer="stitch")
doc.save("szew.svg")
```

### Laserowy wzór ściegu zamiast dziurek

```python
from leathercraft_svg import RoundedRectangle, SvgDocument

doc = SvgDocument(140, 90)
shape = RoundedRectangle(20, 15, 100, 60, radius=10)

doc.add_shape(shape, layer="cut")
doc.add_stitch_pattern(
    shape,
    edges=[0, 2],
    spacing=8.0,
    stitch_length=3.5,
    stitch_angle_deg=45,
    inset=7.0,
    layer="stitch",
    stitch_thickness=0.25,
)
doc.save("stitch_pattern.svg")
```

## DSL dla wzorców

Biblioteka zawiera kompilator DSL (`leathercraft_dsl.py`), który pozwala opisywać wzorce cięcia w prostym formacie tekstowym bez pisania kodu w Pythonie.

### Uruchomienie kompilatora

```bash
python leathercraft_dsl.py build wzorzec.lcraft
```

Polecenie tworzy pliki `wzorzec.svg` i `wzorzec.png` obok pliku źródłowego.

### Podstawowy prostokąt

```text
pattern card_panel
size 120 80

rectangle panel
  at 10 10
  size 100 60
end

stitches
  source panel
  edges all
  margin 4
  spacing 5
  length 3
end

export card_panel
```

### Zaokrąglony prostokąt z ościegami na trzech krawędziach

```text
pattern rounded_pocket
size 120 90

rounded_rectangle pocket
  at 10 10
  size 100 70
  radius 8
end

stitches
  source pocket
  edges except_top
  margin 5
  spacing 5
  length 3.5
  angle 45
end

export rounded_pocket
```

### Dziurki wzdłuż krawędzi figury

```text
holes
  source panel
  edges all
  margin 4
  spacing 6
  radius 1.2
end
```

### Wszystkie wartości podajemy w milimetrach

Nie stosuj przyrostków jednostek takich jak `mm` ani `cm`. Każda liczba jest już w milimetrach.

### Obsługiwane słowa kluczowe

`pattern`, `size`, `layer`, `symmetry`, `rectangle`, `rounded_rectangle`, `outer`, `stitches`, `holes`, `hole`, `export`

Nazwy krawędzi: `top`, `right`, `bottom`, `left`, `all`, `except_top`, `sides`, `horizontal`, `vertical`

Przykładowe pliki `.lcraft` znajdują się w katalogu `examples/dsl/`.

## Kompatybilność

Zachowanie projektu zostało zoptymalizowane pod renderery, które gorzej obsługują CSS w SVG.
Jeśli używasz zewnętrznego narzędzia do rasteryzacji, preferuj narzędzia z dobrą obsługą SVG inline, np. CairoSVG lub Inkscape.

## Struktura plików

- `leathercraft_svg.py` - biblioteka i modele geometryczne,
- `leathercraft_dsl.py` - kompilator DSL (wzorce tekstowe → SVG/PNG),
- `sample.py` - prosty przykład zaokrąglonego prostokąta ze ściegami,
- `all_shapes.py` - przykład poglądowy generujący wszystkie warianty figur,
- `lighter_sleeve.py` - symetryczny wzorzec skórzany z użyciem `Polygon.from_mirror`,
- `examples/dsl/` - przykładowe pliki wzorców `.lcraft`,
- `README.md` - dokumentacja.

## Uwagi praktyczne

- Jeśli chcesz zmienić wygląd elementów, najprościej podać własny słownik `styles` do `SvgDocument`.
- Jeśli chcesz odległości innych niż domyślne, reguluj `spacing` i `inset`.
- Jeśli chcesz gęstsze lub większe dziurki, zmieniaj `hole_radius`.
