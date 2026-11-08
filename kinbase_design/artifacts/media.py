"""Private browser media, kept byte-for-byte without extending package formats."""
from io import BytesIO
from PIL import Image
from ..assets import inspect_format


def image_format(data):
    try:
        return inspect_format(data, 'image')
    except (ValueError,OSError):
        # Modern sites negotiate AVIF and use animated GIF. These originals are
        # valid fidelity references even though the approved manifest is closed.
        try:
            with Image.open(BytesIO(data)) as image:
                extension = {'AVIF': 'avif', 'GIF': 'gif'}.get(image.format)
                image.verify()
        except OSError as exc:
            raise ValueError('Unsupported captured image format') from exc
        if extension:
            return extension
        raise ValueError('Unsupported captured image format')


def selected_responses(responses, candidates):
    """Page media precedes fonts/CSS; unrelated network pixels use no asset budget."""
    wanted = {item['url']: index for index, item in enumerate(candidates) if item.get('url')}
    selected = {}
    for response in responses:
        kind = response.request.resource_type
        if response.url in wanted or kind in {'font', 'stylesheet'}:
            selected[response.url] = response
    return sorted(selected.values(), key=lambda response: (
        0 if response.url in wanted else 1, wanted.get(response.url, len(wanted))))
