from django import template

from apps.embeddings.nodes import cousins as find_cousins

register = template.Library()


@register.inclusion_tag("embeddings/_cousins.html")
def cousins(kind: str, slug: str):
    """{% cousins "grape" grape.slug %} : « ce qui lui ressemble », d'après les vecteurs appris."""
    node_id = f"{kind}:{slug}"
    return {"groups": find_cousins(node_id), "node_id": node_id, "standalone": True}
