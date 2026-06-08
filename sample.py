from leathercraft_svg import RoundedRectangle, SvgDocument


def generate_sample() -> None:
    doc = SvgDocument(width_mm=140, height_mm=90)
    shape = RoundedRectangle(20, 15, 100, 60, radius=10)

    doc.add_shape(shape, layer="cut")

    # RoundedRectangle edges: 0=top, 1=right, 2=bottom, 3=left
    doc.add_stitch_pattern(
        shape,
        edges=[1, 2, 3],  # right, bottom, left
        spacing=15.0,
        stitch_length=3.5,
        stitch_angle_deg=45.0,
        inset=7.0,
        layer="stitch",
        stitch_thickness=0.8,
    )

    doc.save("sample.svg")
    doc.save_png("sample.png", background_color="white")
    print("Generated: sample.svg")
    print("Generated: sample.png")


if __name__ == "__main__":
    generate_sample()
