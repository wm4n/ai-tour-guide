import pytest

from buddy_host.llm.models import ForbiddenModelError, Purpose, resolve_model


def test_defaults_follow_the_design_doc():
    assert resolve_model(Purpose.WRITE, None) == "sonnet"
    assert resolve_model(Purpose.QA, None) == "sonnet"
    assert resolve_model(Purpose.JUDGE, None) == "haiku"


@pytest.mark.parametrize(
    "model", ["sonnet", "haiku", "opus", "claude-sonnet-5-5", "claude-opus-5-5"]
)
def test_allowed_models_pass_through(model):
    assert resolve_model(Purpose.WRITE, model) == model


@pytest.mark.parametrize("model", ["fable", "FABLE", "claude-fable-5-1", "opus-fable", "fable[1m]"])
def test_fable_is_refused(model):
    with pytest.raises(ForbiddenModelError, match="Fable"):
        resolve_model(Purpose.WRITE, model)


@pytest.mark.parametrize("model", ["gpt-5", "", "default", "claude-3-opus"])
def test_unknown_models_are_refused(model):
    with pytest.raises(ForbiddenModelError):
        resolve_model(Purpose.WRITE, model)
