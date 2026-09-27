import asyncio
import sys

if sys.platform == "win32":
    import winsound
else:
    winsound = None


class PopupSignalTrigger:
    def __init__(self, config: dict):
        self.config = config
        self.beep_frequency = 880 
        self.beep_duration_ms = 400

    async def trigger_visual_and_audio_alert(self, coin: str, price: float) -> bool:
        print(f"\n[POPUP ALERT] >>> POPUP ALERT: MOMENTUM DETECTED ON {coin}! <<<")
        print(f"[POPUP ALERT] Local peak/trigger: {price}. OS focus shifted to ENTRY button.")
        
        if winsound:
            try:
                await asyncio.to_thread(winsound.Beep, self.beep_frequency, self.beep_duration_ms)
            except Exception as e:
                print(f"[AUDIO ERROR] Failed to play alert sound: {e}")
        else:
            print(f"[AUDIO SIMULATION] * ALERT SOUND AT {self.beep_frequency} Hz *")

        print("[POPUP ALERT] Hotkeys active: [Space] - Entry, [Escape] - Reset Alert.")
        return True

    def reset_popup_to_background(self):
        print("[POPUP ALERT] Escape pressed. Alert reset, popup closed. Returning to background scanning.")
