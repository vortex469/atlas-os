import axios from "axios";

export const atlas = axios.create({
    baseURL: "/atlas-core",
    timeout: 5000,
});
