package command

import (
	"reflect"
	"testing"
)

// The two domains and the verbs that belong to each. This is the split P-6
// made; the tests below are what keep it made.
var (
	authVerbNames  = []string{"Login", "Logout", "List", "Status"}
	buildVerbNames = []string{"Exec", "RunOne", "RunBatch", "Info", "Materials"}
)

// TestEachDomainTypeExposesItsOwnVerbs is the positive half. Without it the
// negative test below would pass vacuously if a type lost all its methods.
func TestEachDomainTypeExposesItsOwnVerbs(t *testing.T) {
	for _, name := range authVerbNames {
		if _, ok := reflect.TypeFor[*authApp]().MethodByName(name); !ok {
			t.Errorf("authApp is missing %s, one of its own verbs", name)
		}
	}
	for _, name := range buildVerbNames {
		if _, ok := reflect.TypeFor[*buildApp]().MethodByName(name); !ok {
			t.Errorf("buildApp is missing %s, one of its own verbs", name)
		}
	}
}

// TestNeitherDomainTypeExposesTheOthersVerbs pins the boundary. Before P-6 one
// App carried all nine, so nothing stopped a build verb from calling a
// credential one; re-merging the types would fail here.
func TestNeitherDomainTypeExposesTheOthersVerbs(t *testing.T) {
	for _, name := range buildVerbNames {
		if _, ok := reflect.TypeFor[*authApp]().MethodByName(name); ok {
			t.Errorf("authApp exposes %s, a world-building verb", name)
		}
	}
	for _, name := range authVerbNames {
		if _, ok := reflect.TypeFor[*buildApp]().MethodByName(name); ok {
			t.Errorf("buildApp exposes %s, a credential-lifecycle verb", name)
		}
	}
}

// TestBuildAppCannotPromptForASecret guards the one field that is domain-owned
// rather than shared. FieldByName walks embedded structs too, so this fails
// whether PromptSecret is added to buildApp directly or promoted onto base.
func TestBuildAppCannotPromptForASecret(t *testing.T) {
	if _, ok := reflect.TypeFor[buildApp]().FieldByName("PromptSecret"); ok {
		t.Error("buildApp carries PromptSecret — no world-building verb may ask for a secret")
	}
	if _, ok := reflect.TypeFor[authApp]().FieldByName("PromptSecret"); !ok {
		t.Error("authApp lost PromptSecret — `auth login` has no way left to prompt")
	}
}

// TestNeitherDomainTypeCarriesADeadStream records why base has no Stderr:
// failures are rendered by Dispatch's caller, so no verb ever wrote to it. The
// old App carried the field and nothing read it.
func TestNeitherDomainTypeCarriesADeadStream(t *testing.T) {
	for _, typ := range []reflect.Type{reflect.TypeFor[authApp](), reflect.TypeFor[buildApp]()} {
		if _, ok := typ.FieldByName("Stderr"); ok {
			t.Errorf("%s carries Stderr, which no verb writes to — failures go through RenderFailure",
				typ.Name())
		}
	}
}
