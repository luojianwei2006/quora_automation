package com.quora.automation.network;

import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.util.Log;

import com.quora.automation.recording.RecordedAction;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * REST API client for communicating with the management backend.
 * Supports syncing recordings, running tasks, and capturing screenshots.
 */
public class ApiClient {

    private static final String TAG = "ApiClient";
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    private OkHttpClient client;
    private String serverUrl;
    private final Handler mainHandler;
    private String deviceId;

    public ApiClient(String serverUrl) {
        this.serverUrl = serverUrl;
        this.mainHandler = new Handler(Looper.getMainLooper());
        this.deviceId = "android_" + java.util.UUID.randomUUID().toString().substring(0, 8);

        this.client = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .addInterceptor(chain -> {
                    Request original = chain.request();
                    Request request = original.newBuilder()
                            .header("X-Device-ID", deviceId)
                            .header("X-Device-Type", "android")
                            .method(original.method(), original.body())
                            .build();
                    return chain.proceed(request);
                })
                .build();
    }

    public void setServerUrl(String url) {
        this.serverUrl = url;
    }

    /**
     * Test connection to the backend server.
     */
    public void testConnection(final ConnectionCallback callback) {
        Request request = new Request.Builder()
                .url(serverUrl + "/api/browser/status")
                .get()
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                postResult(callback, false);
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                postResult(callback, response.isSuccessful());
                response.close();
            }
        });
    }

    /**
     * Send recorded action to the backend.
     */
    public void sendAction(RecordedAction action) {
        try {
            JSONObject json = action.toJson();
            RequestBody body = RequestBody.create(json.toString(), JSON);
            Request request = new Request.Builder()
                    .url(serverUrl + "/api/recording/add-action")
                    .post(body)
                    .build();

            client.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    Log.e(TAG, "Failed to send action: " + e.getMessage());
                }

                @Override
                public void onResponse(Call call, Response response) {
                    response.close();
                }
            });
        } catch (Exception e) {
            Log.e(TAG, "Error sending action: " + e.getMessage());
        }
    }

    /**
     * Send batch of actions (full recording) to backend.
     */
    public void sendRecording(JSONArray actions, String name, String projectId) {
        try {
            JSONObject json = new JSONObject();
            json.put("name", name);
            json.put("project_id", projectId);

            RequestBody body = RequestBody.create(json.toString(), JSON);
            Request request = new Request.Builder()
                    .url(serverUrl + "/api/recording/save")
                    .post(body)
                    .build();

            // First save the recording header
            client.newCall(request).execute();

            // Then add all actions
            for (int i = 0; i < actions.length(); i++) {
                JSONObject actionJson = actions.getJSONObject(i);
                RequestBody actionBody = RequestBody.create(actionJson.toString(), JSON);
                Request actionRequest = new Request.Builder()
                        .url(serverUrl + "/api/recording/add-action")
                        .post(actionBody)
                        .build();
                client.newCall(actionRequest).execute();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error sending recording: " + e.getMessage());
        }
    }

    /**
     * Send current page info to backend.
     */
    public void sendPageInfo(String url, String title) {
        try {
            JSONObject json = new JSONObject();
            json.put("url", url);
            json.put("title", title);

            RequestBody body = RequestBody.create(json.toString(), JSON);
            Request request = new Request.Builder()
                    .url(serverUrl + "/api/browser/pageinfo")
                    .post(body)
                    .build();

            client.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {}
                @Override
                public void onResponse(Call call, Response response) { response.close(); }
            });
        } catch (Exception ignored) {}
    }

    /**
     * Send screenshot to backend.
     */
    public void sendScreenshot() {
        // Screenshots are handled via the Flask server's screenshot endpoint
        // The Android app captures screenshots locally
        Log.d(TAG, "Screenshot request sent");
    }

    /**
     * Trigger task playback on the backend.
     */
    public void runTask(String taskId, final TaskCallback callback) {
        try {
            JSONObject json = new JSONObject();
            RequestBody body = RequestBody.create(json.toString(), JSON);
            Request request = new Request.Builder()
                    .url(serverUrl + "/api/tasks/" + taskId + "/run")
                    .post(body)
                    .build();

            client.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    postTaskResult(callback, false, e.getMessage());
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    postTaskResult(callback, response.isSuccessful(),
                            response.isSuccessful() ? "Started" : "Failed");
                    response.close();
                }
            });
        } catch (Exception e) {
            postTaskResult(callback, false, e.getMessage());
        }
    }

    // ─── Callback Interfaces ─────────────────────────────

    public interface ConnectionCallback {
        void onResult(boolean success);
    }

    public interface TaskCallback {
        void onResult(boolean success, String message);
    }

    // ─── Helpers ─────────────────────────────────────────

    private void postResult(final ConnectionCallback callback, final boolean success) {
        if (callback != null) {
            mainHandler.post(() -> callback.onResult(success));
        }
    }

    private void postTaskResult(final TaskCallback callback, final boolean success, final String msg) {
        if (callback != null) {
            mainHandler.post(() -> callback.onResult(success, msg));
        }
    }
}
