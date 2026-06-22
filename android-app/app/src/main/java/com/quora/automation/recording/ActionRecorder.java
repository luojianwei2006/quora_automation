package com.quora.automation.recording;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Manages recording of user actions on the mobile browser.
 * Actions can be saved locally and synced to the backend server.
 */
public class ActionRecorder {

    private final Context context;
    private final List<RecordedAction> actions = new ArrayList<>();
    private String currentRecordingId;
    private String currentRecordingName = "Untitled";
    private boolean isRecording = false;
    private int maxActions = 1000;

    public ActionRecorder(Context context) {
        this.context = context;
        loadLocalDraft();
    }

    public void startRecording(String name) {
        this.currentRecordingName = name != null ? name : "Untitled";
        this.currentRecordingId = java.util.UUID.randomUUID().toString().substring(0, 8);
        this.actions.clear();
        this.isRecording = true;
    }

    public void stopRecording() {
        this.isRecording = false;
        saveLocalDraft();
    }

    public boolean isRecording() {
        return isRecording;
    }

    public void addAction(RecordedAction action) {
        if (!isRecording) return;
        if (actions.size() >= maxActions) {
            actions.remove(0); // Remove oldest action
        }
        actions.add(action);
        saveLocalDraft();
    }

    public void removeAction(int index) {
        if (index >= 0 && index < actions.size()) {
            actions.remove(index);
            saveLocalDraft();
        }
    }

    public void updateAction(int index, RecordedAction action) {
        if (index >= 0 && index < actions.size()) {
            actions.set(index, action);
            saveLocalDraft();
        }
    }

    public List<RecordedAction> getActions() {
        return new ArrayList<>(actions);
    }

    public RecordedAction getAction(int index) {
        if (index >= 0 && index < actions.size()) {
            return actions.get(index);
        }
        return null;
    }

    public int getActionCount() {
        return actions.size();
    }

    public void clear() {
        actions.clear();
        saveLocalDraft();
    }

    public String getRecordingId() {
        return currentRecordingId;
    }

    public String getRecordingName() {
        return currentRecordingName;
    }

    /**
     * Export recording as JSON array for API transmission.
     */
    public JSONArray toJsonArray() {
        JSONArray array = new JSONArray();
        for (RecordedAction action : actions) {
            array.put(action.toJson());
        }
        return array;
    }

    /**
     * Save current recording as a local draft.
     */
    private void saveLocalDraft() {
        SharedPreferences prefs = context.getSharedPreferences("recording_draft", Context.MODE_PRIVATE);
        prefs.edit()
                .putString("recording_json", toJsonArray().toString())
                .putString("recording_name", currentRecordingName)
                .putString("recording_id", currentRecordingId)
                .putBoolean("has_draft", true)
                .apply();
    }

    /**
     * Load local draft if available.
     */
    private void loadLocalDraft() {
        SharedPreferences prefs = context.getSharedPreferences("recording_draft", Context.MODE_PRIVATE);
        if (prefs.getBoolean("has_draft", false)) {
            currentRecordingName = prefs.getString("recording_name", "Untitled");
            currentRecordingId = prefs.getString("recording_id", "");
            String json = prefs.getString("recording_json", "[]");
            try {
                JSONArray array = new JSONArray(json);
                actions.clear();
                for (int i = 0; i < array.length(); i++) {
                    JSONObject obj = array.getJSONObject(i);
                    RecordedAction action = new RecordedAction(
                            obj.getString("type"),
                            obj.optInt("x", 0),
                            obj.optInt("y", 0)
                    );
                    // Load all fields
                    if (obj.has("text")) action.setText(obj.getString("text"));
                    if (obj.has("selector")) action.setSelector(obj.getString("selector"));
                    if (obj.has("url")) action.setUrl(obj.getString("url"));
                    if (obj.has("delay_ms")) action.setDelayMs(obj.getInt("delay_ms"));
                    if (obj.has("target_x")) action.setTargetX(obj.getInt("target_x"));
                    if (obj.has("target_y")) action.setTargetY(obj.getInt("target_y"));
                    actions.add(action);
                }
            } catch (Exception ignored) {}
        }
    }
}
