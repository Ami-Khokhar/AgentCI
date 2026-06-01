from unittest.mock import MagicMock
from agentci.data import dataset

def test_build_dataframe_has_metadata_columns():
    df = dataset.build_dataframe()
    for col in ["question", "gold_resolution", "policy_id", "split", "source", "kb"]:
        assert col in df.columns
    assert df["split"].isin(["tune", "held_out"]).all()
    assert (df["kb"].str.len() > 0).all()  # KB embedded for grounded judging

def test_upload_calls_create_dataset(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(dataset, "_client", lambda: client)
    dataset.upload_dataset()
    args, kwargs = client.datasets.create_dataset.call_args
    assert kwargs["input_keys"] == ["question"]
    assert kwargs["output_keys"] == ["gold_resolution"]
