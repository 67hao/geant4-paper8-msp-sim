// ============================================================================
// MyEventAction.hh
// ============================================================================

#ifndef MYEVENTACTION_HH
#define MYEVENTACTION_HH

#include "G4UserEventAction.hh"
#include "globals.hh"
#include <set>

class G4Event;
class MyRunAction;

class MyEventAction : public G4UserEventAction {
public:
    explicit MyEventAction(MyRunAction* runAction);
    ~MyEventAction() override;

    void BeginOfEventAction(const G4Event*) override;
    void EndOfEventAction(const G4Event* event) override;

    // === Flag for first-interaction tracking (used by MySteppingAction) ===
    G4bool IsFirstInteractionRecorded() const { return fFirstInteractionRecorded; }
    void   SetFirstInteractionRecorded()      { fFirstInteractionRecorded = true; }

    // === Primary charged particle in Sample, summed per event (ROOT "Ion" ntuple) ===
    void   AddIonStep(G4double dE, G4double dx) { fIonEdepEvent += dE; fIonPathEvent += dx; }

private:
    MyRunAction* fRunAction;

    std::set<G4int> fCountedNaIDet;
    G4double fEdepEvent = 0.;
    G4bool   fFirstInteractionRecorded = false;   // NEW
    G4double fIonEdepEvent = 0.;
    G4double fIonPathEvent = 0.;
};

#endif // MYEVENTACTION_HH
