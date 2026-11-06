#pragma once
// Presentation states shared by the update owner and the native renderer.
enum class PanelUpdateView { Idle, Available, Checking, Downloading, Current, CheckFailed, Installing, Installed, InstallFailed };
