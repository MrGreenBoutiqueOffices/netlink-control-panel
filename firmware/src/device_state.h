#pragma once

// Confirmed/last-known readings only. There are no requested targets or actions.
struct PanelDeviceState {
  bool heightKnown=false, heightFresh=false, monitorKnown=false, monitorFresh=false;
  int heightMm=0, monitorBrightness=-1;
  char monitorBus[9]={}, monitorPower[9]={}, monitorSource[25]={};
};
