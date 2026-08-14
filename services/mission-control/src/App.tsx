import { RouterProvider } from "react-router-dom";

import { router } from "./app/router";
import { OperatorSessionProvider } from "./hooks/useOperatorSession";

export default function App() {
    return <OperatorSessionProvider><RouterProvider router={router} /></OperatorSessionProvider>;
}
