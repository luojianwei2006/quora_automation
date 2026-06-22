package com.quora.automation.recording;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * Model for a single recorded action step.
 */
public class RecordedAction {
    private String type;
    private int x, y;
    private int targetX, targetY;
    private String text;
    private String selector;
    private String url;
    private String description;
    private int delayMs = 500;
    private int timeoutMs = 10000;
    private int scrollDeltaX, scrollDeltaY;
    private String completionCheckType;
    private String completionCheckValue;
    private boolean retryOnFailure;
    private int maxRetries = 2;

    public RecordedAction(String type, int x, int y) {
        this.type = type;
        this.x = x;
        this.y = y;
    }

    // Getters and setters
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public int getX() { return x; }
    public void setX(int x) { this.x = x; }

    public int getY() { return y; }
    public void setY(int y) { this.y = y; }

    public int getTargetX() { return targetX; }
    public void setTargetX(int targetX) { this.targetX = targetX; }

    public int getTargetY() { return targetY; }
    public void setTargetY(int targetY) { this.targetY = targetY; }

    public String getText() { return text; }
    public void setText(String text) { this.text = text; }

    public String getSelector() { return selector; }
    public void setSelector(String selector) { this.selector = selector; }

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public int getDelayMs() { return delayMs; }
    public void setDelayMs(int delayMs) { this.delayMs = delayMs; }

    public int getTimeoutMs() { return timeoutMs; }
    public void setTimeoutMs(int timeoutMs) { this.timeoutMs = timeoutMs; }

    public int getScrollDeltaX() { return scrollDeltaX; }
    public void setScrollDeltaX(int scrollDeltaX) { this.scrollDeltaX = scrollDeltaX; }

    public int getScrollDeltaY() { return scrollDeltaY; }
    public void setScrollDeltaY(int scrollDeltaY) { this.scrollDeltaY = scrollDeltaY; }

    public String getCompletionCheckType() { return completionCheckType; }
    public void setCompletionCheckType(String type) { this.completionCheckType = type; }

    public String getCompletionCheckValue() { return completionCheckValue; }
    public void setCompletionCheckValue(String value) { this.completionCheckValue = value; }

    public boolean isRetryOnFailure() { return retryOnFailure; }
    public void setRetryOnFailure(boolean retry) { this.retryOnFailure = retry; }

    public int getMaxRetries() { return maxRetries; }
    public void setMaxRetries(int max) { this.maxRetries = max; }

    /**
     * Convert to JSON for sending to the backend server.
     */
    public JSONObject toJson() {
        try {
            JSONObject json = new JSONObject();
            json.put("type", type);
            json.put("x", x);
            json.put("y", y);
            json.put("target_x", targetX);
            json.put("target_y", targetY);
            json.put("text", text != null ? text : "");
            json.put("selector", selector != null ? selector : "");
            json.put("url", url != null ? url : "");
            json.put("description", description != null ? description : "");
            json.put("delay_ms", delayMs);
            json.put("timeout_ms", timeoutMs);
            json.put("scroll_delta_x", scrollDeltaX);
            json.put("scroll_delta_y", scrollDeltaY);
            json.put("completion_check_type", completionCheckType != null ? completionCheckType : "");
            json.put("completion_check_value", completionCheckValue != null ? completionCheckValue : "");
            json.put("retry_on_failure", retryOnFailure);
            json.put("max_retries", maxRetries);
            return json;
        } catch (JSONException e) {
            return new JSONObject();
        }
    }

    @Override
    public String toString() {
        return type + " at (" + x + ", " + y + ")";
    }
}
