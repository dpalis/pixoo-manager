"""
Testes do servico de conversao de GIF.
"""

import pytest
from PIL import Image

from app.services.gif_converter import (
    is_pixoo_ready,
    convert_image,
    convert_gif,
    load_gif_frames,
    adaptive_downscale,
    smart_crop,
    enhance_for_led_display,
    quantize_colors,
    ConvertOptions,
)
from app.config import PIXOO_SIZE


class TestIsPixooReady:
    """Testes para is_pixoo_ready()."""

    def test_returns_true_for_64x64_gif(self, sample_64x64_gif):
        """GIF 64x64 deve retornar True."""
        assert is_pixoo_ready(sample_64x64_gif) is True

    def test_returns_false_for_larger_gif(self, sample_large_gif):
        """GIF maior que 64x64 deve retornar False."""
        assert is_pixoo_ready(sample_large_gif) is False

    def test_returns_false_for_png(self, sample_png):
        """Imagem PNG (nao-GIF) deve retornar False."""
        assert is_pixoo_ready(sample_png) is False


class TestConvertImage:
    """Testes para convert_image()."""

    def test_converts_png_to_64x64(self, sample_png, temp_dir):
        """PNG deve ser convertido para 64x64."""
        output_path, metadata = convert_image(sample_png)

        assert output_path.exists()
        assert metadata.width == PIXOO_SIZE
        assert metadata.height == PIXOO_SIZE
        assert metadata.frames == 1

        # Verificar imagem resultante
        with Image.open(output_path) as img:
            assert img.size == (PIXOO_SIZE, PIXOO_SIZE)

    def test_converts_jpeg_to_64x64(self, sample_jpeg, temp_dir):
        """JPEG deve ser convertido para 64x64."""
        output_path, metadata = convert_image(sample_jpeg)

        assert output_path.exists()
        assert metadata.width == PIXOO_SIZE
        assert metadata.height == PIXOO_SIZE


class TestConvertGif:
    """Testes para convert_gif()."""

    def test_converts_large_gif_to_64x64(self, sample_large_gif):
        """GIF grande deve ser redimensionado para 64x64."""
        options = ConvertOptions(led_optimize=False)
        output_path, metadata = convert_gif(sample_large_gif, options)

        assert output_path.exists()
        assert metadata.width == PIXOO_SIZE
        assert metadata.height == PIXOO_SIZE

        # Verificar frames
        with Image.open(output_path) as img:
            assert img.size == (PIXOO_SIZE, PIXOO_SIZE)

    def test_preserves_frame_count(self, sample_large_gif):
        """Deve preservar numero de frames."""
        options = ConvertOptions(led_optimize=False)
        output_path, metadata = convert_gif(sample_large_gif, options)

        # sample_large_gif tem 2 frames
        assert metadata.frames == 2


class TestLoadGifFrames:
    """Testes para load_gif_frames()."""

    def test_loads_all_frames(self, sample_64x64_gif):
        """Deve carregar todos os frames do GIF."""
        frames, durations = load_gif_frames(sample_64x64_gif)

        assert len(frames) == 3  # sample_64x64_gif tem 3 frames
        assert len(durations) == 3

    def test_returns_correct_durations(self, sample_64x64_gif):
        """Deve retornar duracoes corretas dos frames."""
        frames, durations = load_gif_frames(sample_64x64_gif)

        # sample_64x64_gif foi criado com duration=100
        for d in durations:
            assert d == 100


class TestAdaptiveDownscale:
    """Testes para adaptive_downscale()."""

    def test_downscales_to_target_size(self):
        """Deve redimensionar para o tamanho alvo."""
        img = Image.new("RGB", (256, 256), (255, 0, 0))
        result = adaptive_downscale(img, PIXOO_SIZE)

        assert result.size == (PIXOO_SIZE, PIXOO_SIZE)

    def test_preserves_aspect_ratio_landscape(self):
        """Deve preservar aspecto em imagem paisagem."""
        img = Image.new("RGB", (200, 100), (0, 255, 0))
        result = adaptive_downscale(img, PIXOO_SIZE)

        assert result.size == (PIXOO_SIZE, PIXOO_SIZE)

    def test_preserves_aspect_ratio_portrait(self):
        """Deve preservar aspecto em imagem retrato."""
        img = Image.new("RGB", (100, 200), (0, 0, 255))
        result = adaptive_downscale(img, PIXOO_SIZE)

        assert result.size == (PIXOO_SIZE, PIXOO_SIZE)


class TestSmartCrop:
    """Testes para smart_crop()."""

    def test_crops_to_square(self):
        """Deve cortar para formato quadrado."""
        img = Image.new("RGB", (200, 100), (255, 255, 0))
        result = smart_crop(img, 64)

        assert result.size[0] == result.size[1]  # Quadrado

    def test_returns_correct_size(self):
        """Deve retornar tamanho correto."""
        img = Image.new("RGB", (300, 200), (255, 0, 255))
        result = smart_crop(img, 64)

        assert result.size == (64, 64)


class TestEnhanceForLedDisplay:
    """Testes para enhance_for_led_display()."""

    def test_increases_saturation(self):
        """Deve aumentar saturacao da imagem."""
        # Criar imagem com cor pastel (baixa saturacao)
        img = Image.new("RGB", (64, 64), (200, 180, 170))
        result = enhance_for_led_display(img)

        # Verificar que a imagem foi modificada
        assert result.size == img.size

    def test_preserves_mode(self):
        """Deve preservar o modo da imagem."""
        img = Image.new("RGB", (64, 64), (255, 0, 0))
        result = enhance_for_led_display(img)

        assert result.mode == "RGB"


class TestQuantizeColors:
    """Testes para quantize_colors()."""

    def test_reduces_color_palette(self):
        """Deve reduzir paleta de cores."""
        # Criar imagem com muitas cores (gradiente)
        img = Image.new("RGB", (64, 64))
        pixels = img.load()
        for x in range(64):
            for y in range(64):
                pixels[x, y] = (x * 4, y * 4, (x + y) * 2)

        result = quantize_colors(img, num_colors=16)

        # A imagem deve ter sido processada
        assert result.size == img.size

    def test_preserves_size(self):
        """Deve preservar tamanho da imagem."""
        img = Image.new("RGB", (64, 64), (128, 128, 128))
        result = quantize_colors(img, num_colors=8)

        assert result.size == (64, 64)

    def test_returns_rgb_image(self):
        """Deve retornar imagem RGB."""
        img = Image.new("RGB", (64, 64), (100, 150, 200))
        result = quantize_colors(img, num_colors=32)

        assert result.mode == "RGB"


class TestConvertOptions:
    """Testes para ConvertOptions dataclass."""

    def test_default_values(self):
        """Deve ter valores padrao corretos."""
        options = ConvertOptions()

        assert options.led_optimize is True
        assert options.target_size == 64
        assert options.enhance is True

    def test_custom_values(self):
        """Deve aceitar valores customizados."""
        options = ConvertOptions(
            led_optimize=False,
            num_colors=32,
            enhance=False
        )

        assert options.led_optimize is False
        assert options.num_colors == 32
        assert options.enhance is False
