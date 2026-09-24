import { Text, View } from "react-native";
import { Screen } from "@/src/components/ui";
import { fonts, makeStyles, spacing } from "@/src/theme";

export default function OAuthCallback() {
  const styles = useStyles();
  return (
    <Screen>
      <View style={styles.wrap}>
        <Text style={styles.title}>Concluindo acesso…</Text>
        <Text style={styles.text}>Você será levado de volta ao InovaPro automaticamente.</Text>
      </View>
    </Screen>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  title: { color: colors.onSurface, fontSize: 20, fontFamily: fonts.display },
  text: { color: colors.onSurfaceSecondary, fontSize: 14, fontFamily: fonts.text, textAlign: "center" },
}));
