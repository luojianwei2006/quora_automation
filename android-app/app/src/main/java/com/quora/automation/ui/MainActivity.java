package com.quora.automation.ui;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.quora.automation.R;
import com.quora.automation.network.ApiClient;
import com.quora.automation.recording.ActionRecorder;
import com.quora.automation.recording.RecordedAction;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Main browser simulator activity with floating cursor overlay.
 *
 * Features:
 * - Chrome-like WebView with mobile user agent
 * - Draggable floating cursor for simulating touch
 * - Right-click/long-press context menu for recording
 * - Action playback with step-by-step screenshots
 * - ADB integration for automated testing
 */
public class MainActivity extends AppCompatActivity {

    // UI Components
    private WebView webView;
    private EditText urlBar;
    private FrameLayout browserContainer;
    private LinearLayout actionPanel;

    // Cursor Overlay
    private View cursorOverlay;
    private WindowManager windowManager;
    private WindowManager.LayoutParams cursorParams;
    private boolean cursorActive = false;
    private float cursorX = 200, cursorY = 400;
    private float lastTouchX, lastTouchY;

    // Recording
    private ActionRecorder actionRecorder;
    private List<RecordedAction> recordedActions = new ArrayList<>();
    private boolean isRecording = false;
    private int recordingCursorX, recordingCursorY;

    // API Client
    private ApiClient apiClient;
    private String serverUrl = "http://10.0.2.2:5000"; // Default for emulator

    // Action Panel State
    private boolean actionPanelVisible = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Initialize components
        initViews();
        initWebView();
        initCursorOverlay();
        initApiClient();
        initActionRecorder();

        // Check overlay permission
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                requestOverlayPermission();
            } else {
                showCursorOverlay();
            }
        } else {
            showCursorOverlay();
        }

        // Set up toolbar buttons
        setupToolbar();
    }

    private void initViews() {
        webView = findViewById(R.id.webView);
        urlBar = findViewById(R.id.urlBar);
        browserContainer = findViewById(R.id.browserContainer);
        actionPanel = findViewById(R.id.actionPanel);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void initWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(true);

        // Mobile Chrome emulation user agent
        String mobileUserAgent = "Mozilla/5.0 (Linux; Android 14; SM-S918B) " +
                "AppleWebKit/537.36 (KHTML, like Gecko) " +
                "Chrome/120.0.6099.230 Mobile Safari/537.36";
        settings.setUserAgentString(mobileUserAgent);

        // Enable remote debugging
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                view.loadUrl(request.getUrl().toString());
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                urlBar.setText(url);
                // Notify server of URL change
                apiClient.sendPageInfo(url, view.getTitle());
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onReceivedTitle(WebView view, String title) {
                super.onReceivedTitle(view, title);
            }
        });

        // Default page
        webView.loadUrl("https://www.quora.com");
    }

    private void initCursorOverlay() {
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);

        cursorOverlay = getLayoutInflater().inflate(R.layout.overlay_cursor, null);
        cursorOverlay.setOnTouchListener(new View.OnTouchListener() {
            private float initialX, initialY;
            private float initialTouchX, initialTouchY;
            private long touchStartTime;
            private boolean isDragging = false;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        initialX = cursorParams.x;
                        initialY = cursorParams.y;
                        initialTouchX = event.getRawX();
                        initialTouchY = event.getRawY();
                        touchStartTime = System.currentTimeMillis();
                        isDragging = false;

                        // Update cursor visual state
                        v.setScaleX(0.8f);
                        v.setScaleY(0.8f);
                        return true;

                    case MotionEvent.ACTION_MOVE:
                        float deltaX = event.getRawX() - initialTouchX;
                        float deltaY = event.getRawY() - initialTouchY;

                        // If moved more than threshold, it's a drag
                        if (Math.abs(deltaX) > 10 || Math.abs(deltaY) > 10) {
                            isDragging = true;
                            cursorParams.x = (int) (initialX + deltaX);
                            cursorParams.y = (int) (initialY + deltaY);
                            windowManager.updateViewLayout(v, cursorParams);
                            cursorX = cursorParams.x;
                            cursorY = cursorParams.y;
                        }
                        return true;

                    case MotionEvent.ACTION_UP:
                        v.setScaleX(1.0f);
                        v.setScaleY(1.0f);

                        long touchDuration = System.currentTimeMillis() - touchStartTime;

                        if (!isDragging) {
                            if (touchDuration > 800) {
                                // Long press → show context menu
                                showRecordingMenu();
                            } else if (isRecording) {
                                // Short tap → record as click
                                recordingCursorX = (int) cursorX;
                                recordingCursorY = (int) cursorY;
                                recordAction("click");
                            } else {
                                // Short tap → execute click on WebView
                                executeClickOnWebView((int) cursorX, (int) cursorY);
                            }
                        }
                        return true;
                }
                return false;
            }
        });
    }

    private void initApiClient() {
        apiClient = new ApiClient(serverUrl);
    }

    private void initActionRecorder() {
        actionRecorder = new ActionRecorder(this);
    }

    private void setupToolbar() {
        // Navigate button
        ImageButton goBtn = findViewById(R.id.goButton);
        goBtn.setOnClickListener(v -> {
            String url = urlBar.getText().toString().trim();
            if (!url.isEmpty()) {
                if (!url.startsWith("http://") && !url.startsWith("https://")) {
                    url = "https://" + url;
                }
                webView.loadUrl(url);
            }
        });

        // Refresh button
        ImageButton refreshBtn = findViewById(R.id.refreshButton);
        refreshBtn.setOnClickListener(v -> webView.reload());

        // Record toggle button
        ImageButton recordBtn = findViewById(R.id.recordButton);
        recordBtn.setOnClickListener(v -> {
            isRecording = !isRecording;
            recordBtn.setImageResource(isRecording ?
                    R.drawable.ic_record_active : R.drawable.ic_record);
            Toast.makeText(this,
                    isRecording ? "Recording started" : "Recording stopped",
                    Toast.LENGTH_SHORT).show();
        });

        // Show action panel
        ImageButton actionsBtn = findViewById(R.id.actionsButton);
        actionsBtn.setOnClickListener(v -> toggleActionPanel());

        // Settings / connect to server
        ImageButton settingsBtn = findViewById(R.id.settingsButton);
        settingsBtn.setOnClickListener(v -> showSettingsDialog());
    }

    // ─── Cursor Overlay Management ───────────────────────

    private void requestOverlayPermission() {
        Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()));
        startActivity(intent);
        Toast.makeText(this, "Please grant overlay permission for the cursor", Toast.LENGTH_LONG).show();
    }

    private void showCursorOverlay() {
        if (cursorActive) return;

        cursorParams = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O ?
                        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY :
                        WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE |
                        WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
                PixelFormat.TRANSLUCENT
        );
        cursorParams.gravity = Gravity.TOP | Gravity.START;
        cursorParams.x = (int) cursorX;
        cursorParams.y = (int) cursorY;

        try {
            windowManager.addView(cursorOverlay, cursorParams);
            cursorActive = true;
        } catch (Exception e) {
            Toast.makeText(this, "Failed to show cursor: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void hideCursorOverlay() {
        if (cursorActive && cursorOverlay != null) {
            try {
                windowManager.removeView(cursorOverlay);
                cursorActive = false;
            } catch (Exception ignored) {}
        }
    }

    // ─── WebView Interaction ─────────────────────────────

    private void executeClickOnWebView(int x, int y) {
        // Convert overlay coordinates to WebView coordinates
        int[] location = new int[2];
        webView.getLocationOnScreen(location);

        float webViewX = x - location[0];
        float webViewY = y - location[1];

        // Dispatch touch event to WebView
        long downTime = System.currentTimeMillis();
        MotionEvent downEvent = MotionEvent.obtain(
                downTime, downTime, MotionEvent.ACTION_DOWN,
                webViewX, webViewY, 0);
        webView.dispatchTouchEvent(downEvent);

        MotionEvent upEvent = MotionEvent.obtain(
                downTime, downTime + 50, MotionEvent.ACTION_UP,
                webViewX, webViewY, 0);
        webView.dispatchTouchEvent(upEvent);

        downEvent.recycle();
        upEvent.recycle();

        // Record action if recording
        if (isRecording) {
            recordAction("click", (int) webViewX, (int) webViewY);
        }

        // Send screenshot to server
        captureAndSendScreenshot();
    }

    private void executeLongPressOnWebView(final int x, final int y) {
        int[] location = new int[2];
        webView.getLocationOnScreen(location);

        float webViewX = x - location[0];
        float webViewY = y - location[1];

        long downTime = System.currentTimeMillis();
        MotionEvent downEvent = MotionEvent.obtain(
                downTime, downTime, MotionEvent.ACTION_DOWN,
                webViewX, webViewY, 0);
        webView.dispatchTouchEvent(downEvent);

        // Long press simulation
        webView.postDelayed(() -> {
            MotionEvent upEvent = MotionEvent.obtain(
                    downTime, downTime + 1000, MotionEvent.ACTION_UP,
                    webViewX, webViewY, 0);
            webView.dispatchTouchEvent(upEvent);
            upEvent.recycle();
        }, 800);

        downEvent.recycle();
    }

    // ─── Recording ───────────────────────────────────────

    private void showRecordingMenu() {
        PopupMenu popup = new PopupMenu(this, cursorOverlay, Gravity.CENTER);
        popup.getMenu().add(0, 1, 0, "👆 Click / Tap");
        popup.getMenu().add(0, 2, 0, "👊 Long Press");
        popup.getMenu().add(0, 3, 0, "🔄 Drag");
        popup.getMenu().add(0, 4, 0, "⌨️ Input Text");
        popup.getMenu().add(0, 5, 0, "📋 Paste");
        popup.getMenu().add(0, 6, 0, "📜 Scroll");
        popup.getMenu().add(0, 7, 0, "🌐 Navigate");
        popup.getMenu().add(0, 8, 0, "⏱️ Wait");
        popup.getMenu().add(0, 9, 0, "📄 Copy");
        popup.getMenu().add(0, 10, 0, "📷 Screenshot");
        popup.getMenu().add(0, 11, 0, "📝 Extract Text");
        popup.getMenu().add(0, 12, 0, "✓ Assert Condition");

        popup.setOnMenuItemClickListener(item -> {
            recordingCursorX = (int) cursorX;
            recordingCursorY = (int) cursorY;

            switch (item.getItemId()) {
                case 1: recordAction("click"); break;
                case 2: recordAction("longpress"); break;
                case 3: showDragDialog(); break;
                case 4: showTextInputDialog("input"); break;
                case 5: showTextInputDialog("paste"); break;
                case 6: showScrollDialog(); break;
                case 7: showUrlDialog(); break;
                case 8: recordAction("wait"); break;
                case 9: recordAction("copy"); break;
                case 10: recordAction("screenshot"); break;
                case 11: showExtractDialog(); break;
                case 12: showAssertDialog(); break;
            }
            return true;
        });
        popup.show();
    }

    private void recordAction(String type) {
        RecordedAction action = new RecordedAction(type, recordingCursorX, recordingCursorY);
        recordedActions.add(action);

        // Notify server
        apiClient.sendAction(action);

        String msg = "Recorded: " + type +
                " at (" + recordingCursorX + ", " + recordingCursorY + ")";
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
        updateActionPanel();
    }

    private void recordAction(String type, int x, int y) {
        RecordedAction action = new RecordedAction(type, x, y);
        recordedActions.add(action);
        apiClient.sendAction(action);
        updateActionPanel();
    }

    private void showTextInputDialog(String type) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle(type.equals("input") ? "Input Text" : "Paste Text");

        final EditText input = new EditText(this);
        input.setHint("Enter text...");
        input.setSingleLine(false);
        builder.setView(input);

        builder.setPositiveButton("Record", (dialog, which) -> {
            String text = input.getText().toString();
            RecordedAction action = new RecordedAction(type, recordingCursorX, recordingCursorY);
            action.setText(text);
            recordedActions.add(action);
            apiClient.sendAction(action);
            updateActionPanel();
            Toast.makeText(this, "Recorded: " + type, Toast.LENGTH_SHORT).show();
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private void showDragDialog() {
        // Simple: set target as current + 100px offset
        RecordedAction action = new RecordedAction("drag",
                recordingCursorX, recordingCursorY);
        action.setTargetX(recordingCursorX + 100);
        action.setTargetY(recordingCursorY + 100);
        recordedActions.add(action);
        apiClient.sendAction(action);
        updateActionPanel();
        Toast.makeText(this, "Recorded: drag", Toast.LENGTH_SHORT).show();
    }

    private void showScrollDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Scroll");

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);

        final EditText deltaY = new EditText(this);
        deltaY.setHint("Scroll Y (positive=down, negative=up)");
        deltaY.setText("500");
        layout.addView(deltaY);

        builder.setView(layout);
        builder.setPositiveButton("Record", (dialog, which) -> {
            int scrollY = Integer.parseInt(deltaY.getText().toString());
            RecordedAction action = new RecordedAction("scroll", 0, 0);
            action.setScrollDeltaY(scrollY);
            recordedActions.add(action);
            apiClient.sendAction(action);
            updateActionPanel();
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private void showUrlDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Navigate to URL");

        final EditText input = new EditText(this);
        input.setHint("https://www.quora.com");
        builder.setView(input);

        builder.setPositiveButton("Record", (dialog, which) -> {
            String url = input.getText().toString();
            RecordedAction action = new RecordedAction("navigate", 0, 0);
            action.setUrl(url);
            recordedActions.add(action);
            apiClient.sendAction(action);
            updateActionPanel();
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private void showExtractDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Extract Text");

        final EditText selector = new EditText(this);
        selector.setHint("CSS Selector (e.g., .question-text, body)");
        selector.setText("body");
        builder.setView(selector);

        builder.setPositiveButton("Record", (dialog, which) -> {
            RecordedAction action = new RecordedAction("extract", 0, 0);
            action.setSelector(selector.getText().toString());
            recordedActions.add(action);
            apiClient.sendAction(action);
            updateActionPanel();
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private void showAssertDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Assert Condition");

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);

        final EditText checkType = new EditText(this);
        checkType.setHint("Check type: url_contains / text_contains / selector_visible");
        layout.addView(checkType);

        final EditText checkValue = new EditText(this);
        checkValue.setHint("Expected value");
        layout.addView(checkValue);

        builder.setView(layout);
        builder.setPositiveButton("Record", (dialog, which) -> {
            RecordedAction action = new RecordedAction("assert", 0, 0);
            action.setCompletionCheckType(checkType.getText().toString());
            action.setCompletionCheckValue(checkValue.getText().toString());
            recordedActions.add(action);
            apiClient.sendAction(action);
            updateActionPanel();
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    // ─── Action Panel ────────────────────────────────────

    private void toggleActionPanel() {
        actionPanelVisible = !actionPanelVisible;
        actionPanel.setVisibility(actionPanelVisible ? View.VISIBLE : View.GONE);
        if (actionPanelVisible) updateActionPanel();
    }

    private void updateActionPanel() {
        if (!actionPanelVisible) return;
        // Update action list in the panel
        // This would normally use a RecyclerView
    }

    // ─── Screenshot ──────────────────────────────────────

    private void captureAndSendScreenshot() {
        webView.postDelayed(() -> {
            View view = getWindow().getDecorView().getRootView();
            view.setDrawingCacheEnabled(true);
            // Send to server
            apiClient.sendScreenshot();
        }, 500);
    }

    // ─── Settings ────────────────────────────────────────

    private void showSettingsDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Server Settings");

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);

        final EditText serverInput = new EditText(this);
        serverInput.setHint("Server URL");
        serverInput.setText(serverUrl);
        layout.addView(serverInput);

        final TextView info = new TextView(this);
        info.setText("Connect to management backend to sync recordings and tasks.\n" +
                "Default: http://10.0.2.2:5000 (emulator localhost)");
        info.setTextSize(12);
        info.setPadding(0, 8, 0, 0);
        layout.addView(info);

        builder.setView(layout);
        builder.setPositiveButton("Connect", (dialog, which) -> {
            String newUrl = serverInput.getText().toString().trim();
            if (!newUrl.isEmpty()) {
                serverUrl = newUrl;
                apiClient.setServerUrl(newUrl);
                // Test connection
                apiClient.testConnection(success -> {
                    runOnUiThread(() -> Toast.makeText(this,
                            success ? "Connected to server" : "Connection failed",
                            Toast.LENGTH_SHORT).show());
                });
            }
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    // ─── Lifecycle ───────────────────────────────────────

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        hideCursorOverlay();
        super.onDestroy();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (Settings.canDrawOverlays(this) && !cursorActive) {
                showCursorOverlay();
            }
        }
    }
}
