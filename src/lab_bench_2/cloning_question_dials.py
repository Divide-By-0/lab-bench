"""Render matched CloningQA prompts with independently adjustable difficulty."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class MethodDisclosure(StrEnum):
    """How much the prompt says about the assembly method."""

    NAMED = "named"
    MODEL_CHOOSES = "model_chooses"


class MaterialDisclosure(StrEnum):
    """How candidate plasmids are presented."""

    ROLES_NAMED = "roles_named"
    INVENTORY = "inventory"


class ArchitectureDisclosure(StrEnum):
    """Whether the prompt specifies parts or only required functions."""

    EXACT = "exact"
    FUNCTIONAL = "functional"


@dataclass(frozen=True)
class DifficultyDials:
    """One named combination of independently adjustable prompt dials."""

    name: str
    method: MethodDisclosure
    materials: MaterialDisclosure
    architecture: ArchitectureDisclosure

    def metadata(self) -> dict[str, str]:
        """Return JSON-serializable difficulty metadata."""
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class InventoryItem:
    """One attached material and the information exposed to the model."""

    name: str
    accession: str
    filename: str
    description: str

    def prompt_line(self) -> str:
        """Render this item without assigning it a task-specific role."""
        return (
            f"- {self.name} ({self.accession}; `{self.filename}`): {self.description}"
        )


@dataclass(frozen=True)
class CloningQuestionSpec:
    """Biological content shared by matched difficulty variants."""

    goal: str
    named_backbone_instruction: str
    exact_architecture: tuple[str, ...]
    inventory: tuple[InventoryItem, ...]
    functional_requirements: tuple[str, ...]
    preservation_rule: str
    assembly_method: str


BASELINE = DifficultyDials(
    name="baseline",
    method=MethodDisclosure.NAMED,
    materials=MaterialDisclosure.ROLES_NAMED,
    architecture=ArchitectureDisclosure.EXACT,
)
METHOD_BLIND = DifficultyDials(
    name="method_blind",
    method=MethodDisclosure.MODEL_CHOOSES,
    materials=MaterialDisclosure.ROLES_NAMED,
    architecture=ArchitectureDisclosure.EXACT,
)
INVENTORY_FUNCTIONAL = DifficultyDials(
    name="inventory_functional",
    method=MethodDisclosure.MODEL_CHOOSES,
    materials=MaterialDisclosure.INVENTORY,
    architecture=ArchitectureDisclosure.FUNCTIONAL,
)

DIFFICULTY_PROFILES = (BASELINE, METHOD_BLIND, INVENTORY_FUNCTIONAL)


def render_cloning_question(spec: CloningQuestionSpec, dials: DifficultyDials) -> str:
    """Render one question while keeping its intended final construct fixed."""
    sections = [spec.goal]

    if dials.materials is MaterialDisclosure.ROLES_NAMED:
        sections.append(spec.named_backbone_instruction)
    else:
        inventory = "\n".join(item.prompt_line() for item in spec.inventory)
        sections.append(
            "Choose the necessary materials from this attached inventory; no "
            f"backbone or insert source has been preselected:\n{inventory}"
        )

    if dials.architecture is ArchitectureDisclosure.EXACT:
        sections.extend(spec.exact_architecture)
    else:
        requirements = "; ".join(spec.functional_requirements)
        sections.append(f"The finished construct must provide: {requirements}.")
        sections.append(spec.preservation_rule)

    if dials.method is MethodDisclosure.NAMED:
        sections.append(
            f"Design the components and steps using {spec.assembly_method} assembly"
        )
    else:
        sections.append(
            "Choose an appropriate assembly method, then design the components "
            "and steps. The final construct, rather than use of a particular "
            "method, will be assessed"
        )

    cleaned = [section.rstrip(".") for section in sections]
    if dials.materials is MaterialDisclosure.INVENTORY:
        return ". ".join(cleaned[:2]) + ".\n\n" + ". ".join(cleaned[2:]) + "."
    return ". ".join(cleaned) + "."
